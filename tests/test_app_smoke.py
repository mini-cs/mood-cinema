from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from core.gemini_client import GeminiClient
from core.models import MediaItem, Recommendation, RecommendationList
from core.tmdb_client import TmdbClient

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _media(tmdb_id, media_type="movie", genre_ids=(18,)):
    return MediaItem(tmdb_id, media_type, f"작품{tmdb_id}", f"Work{tmdb_id}", 2019, 7.85, "줄거리", None, None, genre_ids)


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    st.cache_data.clear()
    st.cache_resource.clear()
    for key in ("TMDB_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)  # 프로젝트의 진짜 .env를 읽지 않게


@pytest.fixture
def fakes(monkeypatch):
    trending = [_media(i, "movie" if i % 2 else "tv") for i in range(1, 13)]
    monkeypatch.setattr(TmdbClient, "trending", lambda self, media_type, window: trending)
    monkeypatch.setattr(TmdbClient, "genres", lambda self: {18: "드라마", 28: "액션"})
    monkeypatch.setattr(TmdbClient, "search", lambda self, query, media_type, year=None: [_media(100 + len(query), media_type)])
    recs = RecommendationList(
        items=[
            Recommendation(title_ko="기생충", original_title="Parasite", year=2019, media_type="movie", reason="몰입감 최고"),
            Recommendation(title_ko="아케인", original_title="Arcane", year=2021, media_type="tv", reason="화려한 액션"),
        ]
    )
    monkeypatch.setattr(GeminiClient, "recommend", lambda self, user_text: recs)


def _app_with_keys():
    at = AppTest.from_file(APP, default_timeout=15)
    at.secrets["TMDB_API_KEY"] = "t"
    at.secrets["GEMINI_API_KEY"] = "g"
    return at


def _submit(at, text):
    at.text_area[0].input(text)
    at.form_submit_button[0].click()
    return at.run()


def test_setup_guide_without_keys():
    at = AppTest.from_file(APP, default_timeout=15)
    at.run()
    assert not at.exception
    assert any("TMDB_API_KEY" in x.value for x in at.info)


def test_trending_and_recommendation_render_with_fakes(fakes):
    at = _app_with_keys()
    at.run()
    assert not at.exception
    headings = [h.value for h in at.subheader] + [m.value for m in at.markdown]
    for row in ("오늘의 인기", "이번 주 인기", "장르 픽"):
        assert any(row in h for h in headings), row

    _submit(at, "비 오는 날 스릴러")
    assert not at.exception
    assert any("AI 큐레이터의 한마디" in m.value for m in at.markdown)


def test_cooldown_message_on_quick_resubmit(fakes):
    at = _app_with_keys()
    at.run()
    _submit(at, "비 오는 날 스릴러")
    _submit(at, "주말 가족 드라마")
    assert not at.exception
    assert any("초 후에 다시 추천받을 수 있어요" in w.value for w in at.warning)
