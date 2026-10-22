import itertools
import logging
import math
import time
from pathlib import Path

import streamlit as st
from dotenv import find_dotenv, load_dotenv

from core.config import load_settings
from core.gemini_client import GeminiClient
from core.models import (
    ConfigError,
    GeminiError,
    GeminiFormatError,
    MediaItem,
    RateLimitExceeded,
    RecommendationList,
    RecommendedItem,
    TmdbError,
)
from core.rate_limit import GeminiQuota, check_cooldown
from core.recommender import build_result, validate_query
from core.tmdb_client import TmdbClient, filter_by_genre, image_url

logger = logging.getLogger(__name__)

EXAMPLES = [
    "비 오는 날 혼자 보기 좋은 몰입감 있는 스릴러",
    "야근 끝나고 머리 비우고 싶을 때 볼 가벼운 코미디",
    "주말에 정주행할 감동적인 가족 드라마",
]
MEDIA_TYPES = {"전체": "all", "영화": "movie", "TV": "tv"}
TMDB_LOGO = Path(__file__).parent / "assets" / "tmdb_logo.svg"
TMDB_NOTICE = "This product uses the TMDB API but is not endorsed or certified by TMDB."
GEMINI_NOTICE = "추천 기능은 Google Gemini API 무료 티어를 사용하며, 입력 내용이 Google 제품 개선에 활용될 수 있습니다."


def safe_secrets() -> dict:
    try:
        return dict(st.secrets)
    except FileNotFoundError:  # secrets.toml이 없을 때 (StreamlitSecretNotFoundError)
        return {}


@st.cache_resource
def get_tmdb(api_key: str) -> TmdbClient:
    return TmdbClient(api_key)


@st.cache_resource
def get_gemini(api_key: str, model: str) -> GeminiClient:
    return GeminiClient(api_key, model=model)


@st.cache_resource
def get_quota(rpm: int, daily: int) -> GeminiQuota:
    return GeminiQuota(rpm, daily)


@st.cache_data(ttl=3600, show_spinner=False)
def load_trending(_tmdb: TmdbClient, media_type: str, window: str) -> list[MediaItem]:
    return _tmdb.trending(media_type, window)


@st.cache_data(ttl=86400, show_spinner=False)
def load_genres(_tmdb: TmdbClient) -> dict[int, str]:
    return _tmdb.genres()


@st.cache_data(ttl=86400, show_spinner=False)
def search_media(_tmdb: TmdbClient, query: str, media_type: str, year: int | None) -> list[MediaItem]:
    return _tmdb.search(query, media_type, year)


@st.cache_data(ttl=86400, show_spinner=False)
def load_detail(_tmdb: TmdbClient, tmdb_id: int, media_type: str):
    return _tmdb.detail(tmdb_id, media_type)


@st.cache_data(ttl=3600, show_spinner=False)
def recommend_cached(_gemini: GeminiClient, _quota: GeminiQuota, query: str) -> RecommendationList:
    _quota.acquire()  # 캐시 적중 시엔 본문이 안 돌므로 횟수에 안 들어간다
    return _gemini.recommend(query)


def meta_line(media: MediaItem, genre_names: list[str] | None = None) -> str:
    parts = list(genre_names or [])
    if media.year:
        parts.append(str(media.year))
    parts.append(f"★{media.vote_average:.1f}")
    return " · ".join(parts)


def genre_names_of(media: MediaItem, genre_map: dict[int, str]) -> list[str]:
    return [genre_map[g] for g in media.genre_ids if g in genre_map][:2]


_box_ids = itertools.count()  # 스크립트가 다시 돌 때마다 0부터 → 한 화면 안에서 key가 겹치지 않는다


def box():
    # 테두리 박스는 배경을 칠하지 않으므로, key로 붙는 st-key-box-N 클래스에 inject_css()가 카드 배경을 입힌다
    return st.container(border=True, key=f"box-{next(_box_ids)}")


def inject_css() -> None:
    bg = st.get_option("theme.secondaryBackgroundColor")
    st.html(f'<style>[class*="st-key-box-"] {{ background-color: {bg}; }}</style>')


def render_reason_box(reason: str) -> None:
    with box():
        st.markdown("**🎬 AI 큐레이터의 한마디**")
        st.write(reason)


@st.dialog("작품 상세", width="large")
def show_detail(media: MediaItem, reason: str | None) -> None:
    try:
        detail = load_detail(tmdb, media.tmdb_id, media.media_type)
    except TmdbError:
        logger.exception("TMDB 상세 조회 실패")
        detail = None  # 목록에서 받은 정보만으로 보여준다
    item = detail.item if detail else media

    left, right = st.columns([1, 2])
    with left:
        poster = image_url(item.poster_path, "w500")
        if poster:
            st.image(poster)
        else:
            st.caption("정보 없음")
    with right:
        st.subheader(item.title)
        if item.original_title and item.original_title != item.title:
            st.caption(item.original_title)
        parts = list(detail.genres[:2]) if detail else genre_names_of(item, genre_map)
        if item.year:
            parts.append(str(item.year))
        if detail and detail.runtime_min:
            parts.append(f"{detail.runtime_min}분")
        if detail and detail.seasons:
            parts.append(f"시즌 {detail.seasons}개")
        parts.append(f"★{item.vote_average:.1f}")
        st.write(" · ".join(parts))
        if reason:
            render_reason_box(reason)
        st.write(item.overview or "한국어 줄거리가 등록되지 않았어요")
    if detail and detail.trailer_key:
        st.video(f"https://www.youtube.com/watch?v={detail.trailer_key}")


def render_card(media: MediaItem | None, title: str, reason: str | None, key: str) -> None:
    with box():
        poster = image_url(media.poster_path, "w342") if media else None
        if poster:
            st.image(poster)
        else:
            st.caption("정보 없음")
        st.markdown(f"**{title}**")
        if media:
            st.caption(meta_line(media))
        if reason:
            st.caption(reason)
        if media and st.button("상세 보기", key=f"{key}-{media.media_type}-{media.tmdb_id}"):
            show_detail(media, reason)


def render_hero(item: RecommendedItem, genre_map: dict[int, str]) -> None:
    media = item.media
    left, right = st.columns([3, 2])
    with left:
        image = image_url(media.backdrop_path, "w780") or image_url(media.poster_path, "w500")
        if image:
            st.image(image)
        else:
            st.caption("정보 없음")
    with right:
        st.subheader(item.rec.title_ko)
        st.write(meta_line(media, genre_names_of(media, genre_map)))
        render_reason_box(item.rec.reason)
        if st.button("상세 보기", key=f"hero-{media.media_type}-{media.tmdb_id}"):
            show_detail(media, item.rec.reason)


def request_retry() -> None:
    st.session_state["retry_recommend"] = True


def run_recommend(text: str) -> None:
    try:
        query = validate_query(text)
    except ValueError as e:
        st.warning(str(e))
        return
    try:
        check_cooldown(st.session_state.get("last_recommend_at"), time.time(), settings.recommend_cooldown_sec)
        st.session_state["last_recommend_at"] = time.time()
        st.session_state["last_query"] = query
        with st.spinner("기분에 맞는 작품을 찾고 있어요..."):
            recs = recommend_cached(gemini, quota, query)
            st.session_state["rec_result"] = build_result(recs, lambda q, m, y: search_media(tmdb, q, m, y))
    except RateLimitExceeded as e:
        if e.reason == "cooldown":
            st.warning(f"{math.ceil(e.retry_after_sec)}초 후에 다시 추천받을 수 있어요")
        else:
            st.warning("지금 요청이 많아요. 잠시 후 다시 시도해 주세요")
    except GeminiFormatError:
        logger.exception("Gemini 응답 형식 오류")
        st.error("추천 결과를 읽지 못했어요")
        st.button("다시 시도", on_click=request_retry)
    except GeminiError:
        logger.exception("Gemini 호출 실패")
        st.warning("AI 추천을 불러오지 못했어요. 잠시 후 다시 시도해 주세요")


def render_recommend_section(genre_map: dict[int, str]) -> None:
    st.subheader("AI 추천")
    with st.form("recommend_form"):
        text = st.text_area("지금 기분이나 상황을 적어 주세요", placeholder=EXAMPLES[0])
        submitted = st.form_submit_button("추천받기", type="primary")
    st.caption("예시: " + " / ".join(EXAMPLES))

    if submitted:
        run_recommend(text)
    elif st.session_state.pop("retry_recommend", False):
        run_recommend(st.session_state.get("last_query", ""))

    result = st.session_state.get("rec_result")
    if result is None:
        return
    if result.hero:
        render_hero(result.hero, genre_map)
    if result.others:
        for col, item in zip(st.columns(5), result.others):
            with col:
                title = item.media.title if item.media else item.rec.title_ko
                render_card(item.media, title, item.rec.reason, key="rec")


def render_row(items: list[MediaItem], key: str) -> None:
    for col, media in zip(st.columns(5), items[:5]):
        with col:
            render_card(media, media.title, None, key)
    if len(items) > 5:
        with st.expander("6~10위 더 보기"):
            for col, media in zip(st.columns(5), items[5:10]):
                with col:
                    render_card(media, media.title, None, key)


def render_trending_section(genre_map: dict[int, str]) -> None:
    st.subheader("트렌딩")
    label = st.segmented_control("종류", list(MEDIA_TYPES), default="전체")
    media_type = MEDIA_TYPES.get(label, "all")  # 선택을 해제하면 None → 전체
    try:
        day = load_trending(tmdb, media_type, "day")
        week = load_trending(tmdb, media_type, "week")
    except TmdbError:
        logger.exception("TMDB 트렌딩 조회 실패")
        st.error("인기 작품을 불러오지 못했어요")
        return

    st.markdown("#### 오늘의 인기")
    render_row(day, "day")
    st.markdown("#### 이번 주 인기")
    render_row(week, "week")

    title_col, select_col = st.columns([1, 3])
    title_col.markdown("#### 장르 픽")
    names = sorted(set(genre_map.values()))
    if not names:
        return
    genre = select_col.selectbox(
        "장르", names, index=names.index("드라마") if "드라마" in names else 0, label_visibility="collapsed"
    )
    picked = filter_by_genre(week, genre, genre_map)
    if picked:
        render_row(picked, "genre")
    else:
        st.info("이번 주 인기작 중 이 장르가 없어요")


def render_credits() -> None:
    st.divider()
    st.caption("Credits")
    if TMDB_LOGO.exists():
        st.image(str(TMDB_LOGO), width=80)
    st.caption(TMDB_NOTICE)
    st.caption(GEMINI_NOTICE)


st.set_page_config(page_title="Mood Cinema", page_icon="🎬", layout="wide")
inject_css()
load_dotenv(find_dotenv(usecwd=True))  # 실행 위치 기준으로 .env를 찾는다

try:
    settings = load_settings(safe_secrets())
except ConfigError as e:
    st.error(str(e))
    st.stop()

st.title("🎬 Mood Cinema")
st.caption("지금 기분에 맞는 영화·드라마를 찾아드려요")

missing = settings.missing_keys()
if missing:
    st.info(
        f"API 키가 설정되지 않았어요: {', '.join(missing)}\n\n"
        "설정 방법: .env 또는 Streamlit Secrets에 TMDB_API_KEY / GEMINI_API_KEY 를 등록하세요. "
        "(`.env.example`을 복사해 `.env`로 만들면 됩니다)"
    )

if settings.tmdb_api_key:
    tmdb = get_tmdb(settings.tmdb_api_key)
    try:
        genre_map = load_genres(tmdb)
    except TmdbError:
        logger.exception("TMDB 장르 조회 실패")
        genre_map = {}

    if settings.gemini_api_key:
        gemini = get_gemini(settings.gemini_api_key, settings.gemini_model)
        quota = get_quota(settings.gemini_rpm_limit, settings.gemini_daily_limit)
        render_recommend_section(genre_map)
        st.divider()
    render_trending_section(genre_map)

render_credits()
