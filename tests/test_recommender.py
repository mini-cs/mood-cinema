import pytest

from core.models import MediaItem, Recommendation, RecommendationList, TmdbError
from core.recommender import build_result, match_title, normalize_query, validate_query


def _media(tmdb_id, media_type="movie", title=None, original=None, year=2019):
    title = title or f"작품{tmdb_id}"
    return MediaItem(tmdb_id, media_type, title, original or title, year, 8.0, "", None, None, ())


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
    parasite = _media(496243, title="기생충")
    search = FakeSearch({("기생충", "movie", None): [parasite, _media(1)]})
    assert match_title(_rec("Parasite", "기생충"), search) == parasite
    assert search.calls == [("Parasite", "movie", 2019), ("기생충", "movie", None)]


def test_match_returns_none_when_both_empty():
    assert match_title(_rec("Nope", "없음"), FakeSearch()) is None


def test_match_treats_tmdb_error_as_unmatched():
    assert match_title(_rec("Parasite"), FakeSearch(error=TmdbError("TMDB 요청 실패 (503)"))) is None


def test_build_result_dedupes_same_tmdb_id():
    parasite = _media(496243, title="기생충", original="Parasite")
    search = FakeSearch({("Parasite", "movie", 2019): [parasite], ("기생충", "movie", 2019): [parasite]})
    recs = RecommendationList(items=[_rec("Parasite"), _rec("기생충")])
    result = build_result(recs, search)
    assert result.hero.media.tmdb_id == 496243
    assert result.others == ()


def test_hero_is_first_matched():
    a, b = _media(1, title="A"), _media(2, "tv", title="B")
    search = FakeSearch({("A", "movie", 2019): [a], ("B", "tv", 2019): [b]})
    recs = RecommendationList(items=[_rec("Unknown"), _rec("A"), _rec("B", media_type="tv")])
    result = build_result(recs, search)
    assert result.hero.rec.original_title == "A"
    assert [(i.rec.original_title, i.media) for i in result.others] == [("Unknown", None), ("B", b)]


def test_no_hero_when_all_unmatched():
    recs = RecommendationList(items=[_rec("X"), _rec("Y"), _rec("Y")])
    result = build_result(recs, FakeSearch())
    assert result.hero is None
    assert len(result.others) == 3


def test_match_skips_results_whose_title_differs():
    # 실제 사례: Gemini가 원제를 "Seven"으로 줌 → TMDB 1등은 "황야의 7인"(1960). 한국어 제목 "세븐"으로 찾아야 맞다
    wrong = _media(966, title="황야의 7인", original="The Magnificent Seven", year=1960)
    se7en = _media(807, title="세븐", original="Se7en", year=1995)
    search = FakeSearch({("Seven", "movie", 1995): [wrong], ("세븐", "movie", None): [se7en]})
    assert match_title(_rec("Seven", "세븐", year=1995), search) == se7en


def test_match_none_when_no_title_matches():
    search = FakeSearch({("Seven", "movie", 1995): [_media(1, title="하울링 7", year=1995)], ("세븐", "movie", None): [_media(2, title="세븐 데이즈")]})
    assert match_title(_rec("Seven", "세븐", year=1995), search) is None


def test_match_prefers_same_year_among_title_matches():
    remake = _media(333484, title="매그니피센트 7", original="The Magnificent Seven", year=2016)
    classic = _media(966, title="황야의 7인", original="The Magnificent Seven", year=1960)
    search = FakeSearch({("The Magnificent Seven", "movie", 1960): [remake, classic]})
    assert match_title(_rec("The Magnificent Seven", "황야의 7인", year=1960), search) == classic


def test_title_match_ignores_case_spaces_and_punctuation():
    b99 = _media(48891, "tv", title="브루클린 나인-나인", original="Brooklyn Nine-Nine", year=2013)
    search = FakeSearch({("brooklyn nine nine", "tv", 2013): [b99]})
    assert match_title(_rec("brooklyn nine nine", "브루클린 나인나인", year=2013, media_type="tv"), search) == b99
