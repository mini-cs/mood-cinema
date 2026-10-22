from datetime import datetime

import pytest

from core.config import load_settings
from core.models import ConfigError, MediaDetail, MediaItem, RateLimitExceeded, Recommendation, RecommendationList
from core.rate_limit import PACIFIC, GeminiQuota
from core.service import MoodService, build_service
from core.ttl_cache import TTLCache


def _media(tmdb_id, title, media_type="movie", year=2019):
    return MediaItem(tmdb_id, media_type, title, title, year, 8.0, "", None, None, ())


class FakeTmdb:
    def __init__(self):
        self.calls = {"trending": 0, "genres": 0, "search": 0, "detail": 0}

    def trending(self, media_type, window):
        self.calls["trending"] += 1
        return [_media(1, "기생충")]

    def genres(self):
        self.calls["genres"] += 1
        return {18: "드라마"}

    def search(self, query, media_type, year=None):
        self.calls["search"] += 1
        return [_media(100 + len(query), query, media_type)]

    def detail(self, tmdb_id, media_type):
        self.calls["detail"] += 1
        return MediaDetail(_media(tmdb_id, "기생충"), ("드라마",), 132, None, None)


class FakeGemini:
    def __init__(self):
        self.calls = []

    def recommend(self, query):
        self.calls.append(query)
        return RecommendationList(
            items=[Recommendation(title_ko="기생충", original_title="Parasite", year=2019, media_type="movie", reason="이유")]
        )


def _quota(rpm=5):
    return GeminiQuota(rpm, 200, monotonic=lambda: 0.0, now=lambda: datetime(2026, 10, 22, 12, tzinfo=PACIFIC))


def _service(gemini=True, rpm=5):
    tmdb, fake_gemini = FakeTmdb(), FakeGemini() if gemini else None
    return MoodService(tmdb, fake_gemini, _quota(rpm), cache=TTLCache(clock=lambda: 0.0)), tmdb, fake_gemini


def test_recommend_calls_gemini_and_quota_once_for_same_query():
    service, _, gemini = _service(rpm=1)  # quota가 두 번 불리면 rpm=1에 걸린다
    first = service.recommend("비 오는 날")
    second = service.recommend("비 오는 날")
    assert gemini.calls == ["비 오는 날"]
    assert first.hero.rec.title_ko == second.hero.rec.title_ko == "기생충"


def test_recommend_cache_hit_ignores_full_quota():
    service, _, _ = _service(rpm=1)
    service.recommend("비 오는 날")
    service.recommend("비 오는 날")  # 한도가 꽉 찼어도 캐시 적중이면 성공
    with pytest.raises(RateLimitExceeded) as e:
        service.recommend("주말 가족 드라마")
    assert e.value.reason == "rpm"


def test_recommend_uses_cached_search():
    service, tmdb, _ = _service()
    service.recommend("비 오는 날")
    searches = tmdb.calls["search"]
    service.recommend("비 오는 날")
    assert tmdb.calls["search"] == searches


def test_trending_genres_detail_cached():
    service, tmdb, _ = _service()
    for _ in range(2):
        service.trending("all", "day")
        service.genres()
        service.detail(1, "movie")
    assert tmdb.calls == {"trending": 1, "genres": 1, "search": 0, "detail": 1}


def test_cache_keys_separate_arguments():
    service, tmdb, _ = _service()
    service.trending("all", "day")
    service.trending("movie", "day")
    service.trending("all", "week")
    assert tmdb.calls["trending"] == 3


def test_recommend_without_gemini_raises_config_error():
    service, _, _ = _service(gemini=False)
    assert service.can_recommend is False
    with pytest.raises(ConfigError):
        service.recommend("비 오는 날")


def test_build_service():
    assert build_service(load_settings({}, {})) is None
    tmdb_only = build_service(load_settings({"TMDB_API_KEY": "t"}, {}))
    assert tmdb_only is not None and tmdb_only.can_recommend is False
    both = build_service(load_settings({"TMDB_API_KEY": "t", "GEMINI_API_KEY": "g"}, {}))
    assert both.can_recommend is True
