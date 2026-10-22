from typing import Literal

from core.config import Settings
from core.gemini_client import GeminiClient
from core.models import ConfigError, MediaDetail, MediaItem, RecommendationResult
from core.rate_limit import GeminiQuota
from core.recommender import build_result
from core.tmdb_client import TmdbClient
from core.ttl_cache import TTLCache

TTL_TRENDING = 3600
TTL_GENRES = 86400
TTL_SEARCH = 86400
TTL_DETAIL = 86400
TTL_RECOMMEND = 3600


class MoodService:
    def __init__(self, tmdb: TmdbClient, gemini: GeminiClient | None, quota: GeminiQuota, *, cache: TTLCache | None = None):
        self._tmdb = tmdb
        self._gemini = gemini
        self._quota = quota
        self._cache = cache if cache is not None else TTLCache()  # 빈 캐시는 len()==0이라 `or`를 쓰면 안 된다

    @property
    def can_recommend(self) -> bool:
        return self._gemini is not None

    def trending(self, media_type: Literal["all", "movie", "tv"], window: Literal["day", "week"]) -> list[MediaItem]:
        return self._cache.get_or_set(
            ("trending", media_type, window), TTL_TRENDING, lambda: self._tmdb.trending(media_type, window)
        )

    def genres(self) -> dict[int, str]:
        return self._cache.get_or_set(("genres",), TTL_GENRES, self._tmdb.genres)

    def search(self, query: str, media_type: Literal["movie", "tv"], year: int | None) -> list[MediaItem]:
        return self._cache.get_or_set(
            ("search", query, media_type, year), TTL_SEARCH, lambda: self._tmdb.search(query, media_type, year)
        )

    def detail(self, tmdb_id: int, media_type: Literal["movie", "tv"]) -> MediaDetail:
        return self._cache.get_or_set(
            ("detail", tmdb_id, media_type), TTL_DETAIL, lambda: self._tmdb.detail(tmdb_id, media_type)
        )

    def recommend(self, query: str) -> RecommendationResult:
        if self._gemini is None:
            raise ConfigError("GEMINI_API_KEY가 설정되지 않았어요")

        def ask_gemini():
            self._quota.acquire()  # 캐시에 없을 때만 횟수를 센다
            return self._gemini.recommend(query)

        recs = self._cache.get_or_set(("recommend", query), TTL_RECOMMEND, ask_gemini)
        return build_result(recs, self.search)


def build_service(settings: Settings) -> MoodService | None:
    if not settings.tmdb_api_key:
        return None
    gemini = GeminiClient(settings.gemini_api_key, model=settings.gemini_model) if settings.gemini_api_key else None
    quota = GeminiQuota(settings.gemini_rpm_limit, settings.gemini_daily_limit)
    return MoodService(TmdbClient(settings.tmdb_api_key), gemini, quota)
