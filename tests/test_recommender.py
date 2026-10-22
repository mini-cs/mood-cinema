import pytest

from core.models import MediaItem, Recommendation, RecommendationList, TmdbError
from core.recommender import build_result, match_title, normalize_query, validate_query


def _media(tmdb_id, media_type="movie"):
    return MediaItem(tmdb_id, media_type, f"작품{tmdb_id}", f"Work{tmdb_id}", 2019, 8.0, "", None, None, ())


def _rec(original, ko=None, year=2019, media_type="movie"):
    return Recommendation(title_ko=ko or original, original_title=original, year=year, media_type=media_type, reason="이유")


class FakeSearch:
    """(query, media_type, year) → 결과 목록. 없는 키는 []. 호출을 기록한다."""

    def __init__(self, results=None, error=None):
        self.results = results or {}
        self.error = error
        self.calls = []

    def __call__(self, query, media_type, year):
        self.calls.append((query, media_type, year))
        if self.error:
            raise self.error
        return self.results.get((query, media_type, year), [])


def test_normalize_query():
    assert normalize_query("  비 오는\n\n날  ") == "비 오는 날"


def test_validate_query_empty():
    with pytest.raises(ValueError, match="추천받고 싶은 기분이나 상황을 적어 주세요."):
        validate_query("   \n\t")


def test_validate_query_length():
    assert validate_query("가" * 300) == "가" * 300
    with pytest.raises(ValueError, match="300자 이내로 적어 주세요."):
        validate_query("가" * 301)


def test_match_falls_back_to_korean_title():
    search = FakeSearch({("기생충", "movie", None): [_media(496243), _media(1)]})
    assert match_title(_rec("Parasite", "기생충"), search) == _media(496243)
    assert search.calls == [("Parasite", "movie", 2019), ("기생충", "movie", None)]


def test_match_returns_none_when_both_empty():
    assert match_title(_rec("Nope", "없음"), FakeSearch()) is None


def test_match_treats_tmdb_error_as_unmatched():
    assert match_title(_rec("Parasite"), FakeSearch(error=TmdbError("TMDB 요청 실패 (503)"))) is None


def test_build_result_dedupes_same_tmdb_id():
    search = FakeSearch({("Parasite", "movie", 2019): [_media(496243)], ("기생충", "movie", 2019): [_media(496243)]})
    recs = RecommendationList(items=[_rec("Parasite"), _rec("기생충")])
    result = build_result(recs, search)
    assert result.hero.media.tmdb_id == 496243
    assert result.others == ()


def test_hero_is_first_matched():
    search = FakeSearch({("A", "movie", 2019): [_media(1)], ("B", "tv", 2019): [_media(2, "tv")]})
    recs = RecommendationList(items=[_rec("Unknown"), _rec("A"), _rec("B", media_type="tv")])
    result = build_result(recs, search)
    assert result.hero.rec.original_title == "A"
    assert [(i.rec.original_title, i.media) for i in result.others] == [("Unknown", None), ("B", _media(2, "tv"))]


def test_no_hero_when_all_unmatched():
    recs = RecommendationList(items=[_rec("X"), _rec("Y"), _rec("Y")])
    result = build_result(recs, FakeSearch())
    assert result.hero is None
    assert len(result.others) == 3
