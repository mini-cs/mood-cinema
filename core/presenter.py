from collections.abc import Sequence
from dataclasses import dataclass

from core.models import MediaDetail, MediaItem, RecommendedItem
from core.tmdb_client import image_url

NO_OVERVIEW = "한국어 줄거리가 등록되지 않았어요"


# 화면(Reflex State)으로 보내는 값이라 문자열·숫자·불리언만 쓰고, 없는 값은 None 대신 빈 문자열로 둔다
@dataclass
class CardVM:
    key: str = ""
    tmdb_id: int = 0
    media_type: str = ""
    title: str = ""
    meta: str = ""
    poster_url: str = ""
    reason: str = ""
    rank: int = 0
    clickable: bool = False


@dataclass
class HeroVM:
    tmdb_id: int = 0
    media_type: str = ""
    title: str = ""
    meta: str = ""
    backdrop_url: str = ""
    reason: str = ""


@dataclass
class DetailVM:
    title: str = ""
    original_title: str = ""
    meta: str = ""
    overview: str = ""
    poster_url: str = ""
    backdrop_url: str = ""
    reason: str = ""
    trailer_embed_url: str = ""


def meta_line(year: int | None, vote_average: float, *, genres: Sequence[str] = (), extra: Sequence[str] = ()) -> str:
    parts = [*genres[:2], *([str(year)] if year else []), *extra, f"★{vote_average:.1f}"]
    return " · ".join(parts)


def genre_names(media: MediaItem, genre_map: dict[int, str]) -> list[str]:
    return [genre_map[g] for g in media.genre_ids if g in genre_map][:2]


def card_key(prefix: str, media: MediaItem) -> str:
    return f"{prefix}-{media.media_type}-{media.tmdb_id}"


def _card(media: MediaItem, key: str, *, reason: str = "", rank: int = 0) -> CardVM:
    return CardVM(
        key=key,
        tmdb_id=media.tmdb_id,
        media_type=media.media_type,
        title=media.title,
        meta=meta_line(media.year, media.vote_average),
        poster_url=image_url(media.poster_path, "w342") or "",
        reason=reason,
        rank=rank,
        clickable=True,
    )


def trending_cards(items: Sequence[MediaItem], key: str, *, ranked: bool, limit: int = 10) -> list[CardVM]:
    return [
        _card(media, card_key(key, media), rank=i if ranked else 0) for i, media in enumerate(items[:limit], start=1)
    ]


def recommended_cards(items: Sequence[RecommendedItem]) -> list[CardVM]:
    cards = []
    for i, item in enumerate(items):
        if item.media is None:  # TMDB 미확인: 누를 수 없는 "정보 없음" 카드
            cards.append(CardVM(key=f"rec-unmatched-{i}", title=item.rec.title_ko, reason=item.rec.reason))
        else:
            cards.append(_card(item.media, card_key("rec", item.media), reason=item.rec.reason))
    return cards


def hero_view(item: RecommendedItem, genre_map: dict[int, str]) -> HeroVM:
    media = item.media
    return HeroVM(
        tmdb_id=media.tmdb_id,
        media_type=media.media_type,
        title=item.rec.title_ko,
        meta=meta_line(media.year, media.vote_average, genres=genre_names(media, genre_map)),
        backdrop_url=image_url(media.backdrop_path, "w1280") or image_url(media.poster_path, "w780") or "",
        reason=item.rec.reason,
    )


def detail_view(detail: MediaDetail, reason: str = "") -> DetailVM:
    item = detail.item
    extra = [f"{detail.runtime_min}분"] if detail.runtime_min else []
    if detail.seasons:
        extra.append(f"시즌 {detail.seasons}개")
    return DetailVM(
        title=item.title,
        original_title="" if item.original_title == item.title else item.original_title,
        meta=meta_line(item.year, item.vote_average, genres=detail.genres[:2], extra=extra),
        overview=item.overview or NO_OVERVIEW,
        poster_url=image_url(item.poster_path, "w342") or "",
        backdrop_url=image_url(item.backdrop_path, "w1280") or "",
        reason=reason,
        trailer_embed_url=f"https://www.youtube.com/embed/{detail.trailer_key}" if detail.trailer_key else "",
    )
