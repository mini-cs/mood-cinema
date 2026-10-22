import time
from collections.abc import Callable
from typing import Literal

import requests

from core.models import MediaDetail, MediaItem, TmdbError
from core.rate_limit import RETRYABLE_STATUS, parse_retry_after, with_backoff

BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p"

# 영화와 TV는 필드 이름이 다르다: (제목, 원제, 날짜)
_FIELDS = {
    "movie": ("title", "original_title", "release_date"),
    "tv": ("name", "original_name", "first_air_date"),
}


def image_url(path: str | None, size: str) -> str | None:
    return f"{IMAGE_BASE}/{size}{path}" if path else None


def parse_media_item(raw: dict, media_type: str | None = None) -> MediaItem | None:
    media_type = media_type or raw.get("media_type")
    if media_type not in _FIELDS:
        return None
    title_key, original_key, date_key = _FIELDS[media_type]
    date = raw.get(date_key) or ""
    return MediaItem(
        tmdb_id=raw["id"],
        media_type=media_type,
        title=raw.get(title_key) or "",
        original_title=raw.get(original_key) or "",
        year=int(date[:4]) if date[:4].isdigit() else None,
        vote_average=float(raw.get("vote_average") or 0.0),
        overview=raw.get("overview") or "",
        poster_path=raw.get("poster_path"),
        backdrop_path=raw.get("backdrop_path"),
        # 목록 응답은 genre_ids, 상세 응답은 genres[{id, name}]
        genre_ids=tuple(raw.get("genre_ids") or [g["id"] for g in raw.get("genres") or []]),
    )


def filter_by_genre(items: list[MediaItem], genre_name: str, genre_map: dict[int, str]) -> list[MediaItem]:
    return [i for i in items if any(genre_map.get(g) == genre_name for g in i.genre_ids)]


def pick_trailer(videos: list[dict]) -> str | None:
    youtube = [v for v in videos if v.get("site") == "YouTube"]
    trailers = [v for v in youtube if v.get("type") == "Trailer"]
    best = (trailers or youtube or [None])[0]
    return best["key"] if best else None


class TmdbClient:
    def __init__(
        self,
        api_key: str,
        *,
        session: requests.Session | None = None,
        language: str = "ko-KR",
        timeout: float = 10.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._api_key = api_key
        self._session = session or requests.Session()
        self._language = language
        self._timeout = timeout
        self._sleep = sleep

    def _get(self, path: str, params: dict | None = None) -> dict:
        query = {"api_key": self._api_key, "language": self._language, **(params or {})}

        def call() -> dict:
            # requests 예외 문자열엔 api_key가 든 URL이 있으므로 메시지를 직접 만들고 원본은 끊는다
            try:
                resp = self._session.get(f"{BASE_URL}{path}", params=query, timeout=self._timeout)
            except (requests.ConnectionError, requests.Timeout):
                raise TmdbError("TMDB 연결 실패", retryable=True) from None
            except requests.RequestException:
                raise TmdbError("TMDB 요청 실패") from None
            if resp.status_code >= 400:
                raise TmdbError(
                    f"TMDB 요청 실패 ({resp.status_code})",
                    status=resp.status_code,
                    retry_after=parse_retry_after(resp.headers.get("Retry-After")),
                    retryable=resp.status_code in RETRYABLE_STATUS,
                )
            try:
                return resp.json()
            except ValueError:
                raise TmdbError(f"TMDB 응답 해석 실패 ({resp.status_code})", status=resp.status_code) from None

        return with_backoff(call, sleep=self._sleep)

    def _parse_results(self, data: dict, media_type: str | None) -> list[MediaItem]:
        items = (parse_media_item(raw, media_type) for raw in data.get("results") or [])
        return [i for i in items if i is not None]

    def trending(self, media_type: Literal["all", "movie", "tv"], window: Literal["day", "week"]) -> list[MediaItem]:
        data = self._get(f"/trending/{media_type}/{window}")
        return self._parse_results(data, None if media_type == "all" else media_type)

    def genres(self) -> dict[int, str]:
        genre_map = {}
        for media_type in ("movie", "tv"):
            genre_map.update({g["id"]: g["name"] for g in self._get(f"/genre/{media_type}/list").get("genres", [])})
        return genre_map

    def search(self, query: str, media_type: Literal["movie", "tv"], year: int | None = None) -> list[MediaItem]:
        params = {"query": query}
        if year is not None:
            params["year" if media_type == "movie" else "first_air_date_year"] = year
        return self._parse_results(self._get(f"/search/{media_type}", params), media_type)

    def detail(self, tmdb_id: int, media_type: Literal["movie", "tv"]) -> MediaDetail:
        raw = self._get(f"/{media_type}/{tmdb_id}", {"append_to_response": "videos", "include_video_language": "ko,en"})
        return MediaDetail(
            item=parse_media_item(raw, media_type),
            genres=tuple(g["name"] for g in raw.get("genres") or []),
            runtime_min=raw.get("runtime") if media_type == "movie" else None,
            seasons=raw.get("number_of_seasons") if media_type == "tv" else None,
            trailer_key=pick_trailer((raw.get("videos") or {}).get("results") or []),
        )
