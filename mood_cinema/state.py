import asyncio
import functools
import logging
import math
import time

import reflex as rx
from dotenv import find_dotenv, load_dotenv

from core.config import load_settings
from core.models import ConfigError, GeminiError, GeminiFormatError, MediaItem, RateLimitExceeded, TmdbError
from core.presenter import CardVM, DetailVM, HeroVM, detail_view, hero_view, recommended_cards, trending_cards
from core.rate_limit import check_cooldown
from core.recommender import validate_query
from core.service import MoodService, build_service
from core.tmdb_client import filter_by_genre

logger = logging.getLogger(__name__)

load_dotenv(find_dotenv(usecwd=True))  # 실행 위치 기준으로 .env를 찾는다

MEDIA_TYPES = {"전체": "all", "영화": "movie", "TV": "tv"}


@functools.cache
def get_service() -> MoodService | None:
    # 키·클라이언트는 여기(백엔드 프로세스)에만 둔다. State 변수에 넣으면 브라우저로 전송된다
    return build_service(load_settings())


class State(rx.State):
    missing_keys: list[str] = []
    config_error: str = ""

    @rx.event
    def check_setup(self):
        try:
            self.missing_keys = load_settings().missing_keys()
        except ConfigError as e:
            self.config_error = str(e)


class TrendingState(State):
    media_label: str = "전체"
    genre: str = "드라마"
    genre_options: list[str] = []
    day: list[CardVM] = []
    week: list[CardVM] = []
    genre_pick: list[CardVM] = []
    loading: bool = False
    error: str = ""

    # 밑줄로 시작하는 변수는 백엔드에만 있고 브라우저로 보내지 않는다
    _week_items: list[MediaItem] = []
    _genre_map: dict[int, str] = {}

    @rx.event(background=True)
    async def load(self):
        async with self:
            label = self.media_label
            self.loading = True
            self.error = ""
        try:
            service = get_service()
            if service is None:  # TMDB 키 없음: 안내는 check_setup이 보여준다
                async with self:
                    self.loading = False
                return
            media_type = MEDIA_TYPES[label]
            genre_map = await asyncio.to_thread(service.genres)
            day = await asyncio.to_thread(service.trending, media_type, "day")
            week = await asyncio.to_thread(service.trending, media_type, "week")
        except (TmdbError, ConfigError):
            logger.exception("트렌딩 조회 실패")
            async with self:
                if self.media_label == label:
                    self.error = "인기 작품을 불러오지 못했어요"
                    self.loading = False
            return

        async with self:
            if self.media_label != label:
                return  # 그사이 종류가 바뀌었다. 늦게 끝난 이전 요청이 최신 결과를 덮어쓰지 않게 버린다
            self._genre_map = genre_map
            self._week_items = week
            self.genre_options = sorted(set(genre_map.values()))
            if self.genre not in self.genre_options and self.genre_options:
                self.genre = self.genre_options[0]
            self.day = trending_cards(day, "day", ranked=True)
            self.week = trending_cards(week, "week", ranked=True)
            self.genre_pick = trending_cards(filter_by_genre(week, self.genre, genre_map), "genre", ranked=False)
            self.loading = False

    @rx.event
    def set_media(self, label: str | list[str]):
        # 0.10의 segmented_control은 str | list[str]을 넘긴다 (단일 선택이라 실제로는 str)
        self.media_label = label if isinstance(label, str) else label[0]
        return TrendingState.load

    @rx.event
    def set_genre(self, name: str):
        self.genre = name
        # API를 다시 부르지 않고 이미 받은 이번 주 인기에서 다시 거른다
        self.genre_pick = trending_cards(filter_by_genre(self._week_items, name, self._genre_map), "genre", ranked=False)


def _rate_limit_message(e: RateLimitExceeded) -> str:
    if e.reason == "cooldown":
        return f"{math.ceil(e.retry_after_sec)}초 후에 다시 추천받을 수 있어요"
    return "지금 요청이 많아요. 잠시 후 다시 시도해 주세요"


class RecommendState(State):
    query: str = ""
    loading: bool = False
    warning: str = ""
    error: str = ""
    can_retry: bool = False
    has_hero: bool = False
    hero: HeroVM = HeroVM()
    cards: list[CardVM] = []

    _last_recommend_at: float | None = None
    _last_query: str = ""

    @rx.event
    def set_query(self, text: str):
        self.query = text

    @rx.event
    def use_example(self, text: str):
        self.query = text  # 입력창만 채운다. 바로 요청하지 않는다

    @rx.event(background=True)
    async def submit(self):
        async with self:
            text = self.query
        await self._recommend(text)

    @rx.event(background=True)
    async def retry(self):
        async with self:
            text = self._last_query
        await self._recommend(text)

    async def _recommend(self, text: str):
        async with self:
            if self.loading:
                return  # 로딩 중 연타: 요청은 한 번만
            self.warning, self.error, self.can_retry = "", "", False
            try:
                query = validate_query(text)
                check_cooldown(self._last_recommend_at, time.time(), load_settings().recommend_cooldown_sec)
            except ValueError as e:
                self.warning = str(e)
                return
            except RateLimitExceeded as e:
                self.warning = _rate_limit_message(e)
                return
            self._last_recommend_at = time.time()
            self._last_query = query
            self.loading = True

        result, genre_map = None, {}
        warning, error, can_retry = "", "", False
        try:
            service = get_service()
            if service is None:
                raise ConfigError("TMDB_API_KEY가 설정되지 않았어요")
            result = await asyncio.to_thread(service.recommend, query)
            genre_map = await asyncio.to_thread(service.genres)
        except RateLimitExceeded as e:
            warning = _rate_limit_message(e)
        except GeminiFormatError:
            logger.exception("Gemini 응답 형식 오류")
            error, can_retry = "추천 결과를 읽지 못했어요", True
        except GeminiError:
            logger.exception("Gemini 호출 실패")
            warning = "AI 추천을 불러오지 못했어요. 잠시 후 다시 시도해 주세요"
        except TmdbError:
            logger.exception("TMDB 장르 조회 실패")  # 추천은 받았으니 장르 없이 보여준다
        except ConfigError as e:
            warning = str(e)
        finally:
            # 예상 못한 예외가 나도 버튼이 '로딩 중'으로 잠긴 채 남지 않게 한다
            async with self:
                self.warning, self.error, self.can_retry = warning, error, can_retry
                if result is not None:
                    self.has_hero = result.hero is not None
                    self.hero = hero_view(result.hero, genre_map) if result.hero else HeroVM()
                    self.cards = recommended_cards(result.others)
                self.loading = False


class DetailState(State):
    open: bool = False
    loading: bool = False
    error: str = ""
    view: DetailVM = DetailVM()

    _request: str = ""  # 지금 열려 있는 작품. 늦게 끝난 이전 요청이 덮어쓰지 않게 비교한다

    @rx.event(background=True)
    async def open_detail(self, media_type: str, tmdb_id: int, reason: str):
        request = f"{media_type}-{tmdb_id}"
        async with self:
            # 열 때마다 비운다: B가 실패해도 이전에 본 A 내용이 남지 않게
            self.view, self.loading, self.error, self.open = DetailVM(), True, "", True
            self._request = request

        view, error = None, ""
        try:
            service = get_service()
            if service is None:
                raise ConfigError("TMDB_API_KEY가 설정되지 않았어요")
            view = detail_view(await asyncio.to_thread(service.detail, tmdb_id, media_type), reason)
        except (TmdbError, ConfigError):
            logger.exception("상세 조회 실패")
            error = "상세 정보를 불러오지 못했어요"
        finally:
            async with self:
                if self._request == request:
                    self.view = view or DetailVM()
                    self.error = error
                    self.loading = False

    @rx.event
    def set_open(self, value: bool):
        self.open = value
