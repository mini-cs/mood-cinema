from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


class ConfigError(Exception):
    pass


class RateLimitExceeded(Exception):
    def __init__(self, reason: Literal["cooldown", "rpm", "daily"], retry_after_sec: float):
        super().__init__(f"rate limit: {reason} (retry after {retry_after_sec:.0f}s)")
        self.reason = reason
        self.retry_after_sec = retry_after_sec


class ApiError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retry_after: float | None = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.message = message
        self.status = status
        self.retry_after = retry_after
        self.retryable = retryable


class TmdbError(ApiError):
    pass


class GeminiError(ApiError):
    pass


class GeminiFormatError(GeminiError):
    pass


class Recommendation(BaseModel):
    title_ko: str  # 한국어 제목 (없으면 원제 그대로)
    original_title: str  # 원제 (TMDB 검색용)
    year: int | None  # 개봉/첫 방영 연도
    media_type: Literal["movie", "tv"]
    reason: str  # 추천 이유 (한국어 1~2문장)


class RecommendationList(BaseModel):
    items: list[Recommendation] = Field(min_length=1, max_length=5)


@dataclass(frozen=True)
class MediaItem:
    tmdb_id: int
    media_type: Literal["movie", "tv"]
    title: str
    original_title: str
    year: int | None
    vote_average: float
    overview: str
    poster_path: str | None
    backdrop_path: str | None
    genre_ids: tuple[int, ...]


@dataclass(frozen=True)
class MediaDetail:
    item: MediaItem
    genres: tuple[str, ...]
    runtime_min: int | None
    seasons: int | None
    trailer_key: str | None


@dataclass(frozen=True)
class RecommendedItem:
    rec: Recommendation
    media: MediaItem | None  # None = TMDB 미확인


@dataclass(frozen=True)
class RecommendationResult:
    hero: RecommendedItem | None
    others: tuple[RecommendedItem, ...]
