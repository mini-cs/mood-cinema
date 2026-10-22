from collections.abc import Callable
from typing import Literal

from core.models import MediaItem, Recommendation, RecommendationList, RecommendationResult, RecommendedItem, TmdbError

MAX_QUERY_LEN = 300

SearchFn = Callable[[str, Literal["movie", "tv"], int | None], list[MediaItem]]


def normalize_query(text: str) -> str:
    return " ".join(text.split())


def validate_query(text: str) -> str:
    query = normalize_query(text)
    if not query:
        raise ValueError("추천받고 싶은 기분이나 상황을 적어 주세요.")
    if len(query) > MAX_QUERY_LEN:
        raise ValueError("300자 이내로 적어 주세요.")
    return query


def match_title(rec: Recommendation, search: SearchFn) -> MediaItem | None:
    try:
        results = search(rec.original_title, rec.media_type, rec.year) or search(rec.title_ko, rec.media_type, None)
    except TmdbError:
        return None
    return results[0] if results else None


def build_result(recs: RecommendationList, search: SearchFn) -> RecommendationResult:
    items: list[RecommendedItem] = []
    seen: set[tuple[str, int]] = set()
    for rec in recs.items:
        media = match_title(rec, search)
        if media is not None:
            key = (media.media_type, media.tmdb_id)
            if key in seen:
                continue
            seen.add(key)
        items.append(RecommendedItem(rec=rec, media=media))
    hero = next((i for i in items if i.media is not None), None)
    return RecommendationResult(hero=hero, others=tuple(i for i in items if i is not hero))
