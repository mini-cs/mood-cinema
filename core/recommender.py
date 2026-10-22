import re
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


def _title_key(title: str) -> str:
    """대소문자·공백·문장부호를 무시하고 비교하기 위한 키. "Nine-Nine" == "nine nine"."""
    return re.sub(r"[\W_]+", "", title).casefold()


def _pick(results: list[MediaItem], rec: Recommendation) -> MediaItem | None:
    # 검색 1등이 엉뚱한 작품일 수 있다 ("Seven" → 황야의 7인). 제목이 실제로 같은 결과만 받고, 그중 연도가 맞는 것을 먼저 고른다
    names = {_title_key(rec.original_title), _title_key(rec.title_ko)} - {""}
    matched = [m for m in results if names & {_title_key(m.title), _title_key(m.original_title)}]
    same_year = [m for m in matched if rec.year and m.year == rec.year]
    return (same_year or matched or [None])[0]


def match_title(rec: Recommendation, search: SearchFn) -> MediaItem | None:
    try:
        return _pick(search(rec.original_title, rec.media_type, rec.year), rec) or _pick(
            search(rec.title_ko, rec.media_type, None), rec
        )
    except TmdbError:
        return None


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
