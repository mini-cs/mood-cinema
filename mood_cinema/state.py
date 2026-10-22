import asyncio
import functools
import logging

import reflex as rx
from dotenv import find_dotenv, load_dotenv

from core.config import load_settings
from core.models import ConfigError, MediaItem, TmdbError
from core.presenter import CardVM, trending_cards
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
