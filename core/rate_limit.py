import random
import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TypeVar
from zoneinfo import ZoneInfo

from core.models import ApiError, RateLimitExceeded

T = TypeVar("T")

RETRYABLE_STATUS: frozenset[int] = frozenset({429, 500, 502, 503, 504})
PACIFIC = ZoneInfo("America/Los_Angeles")


def parse_retry_after(value: str | None) -> float | None:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None  # HTTP 날짜 형식도 여기로 온다
    return seconds if seconds >= 0 else None


def with_backoff(
    call: Callable[[], T],
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 20.0,
    sleep: Callable[[float], None] = time.sleep,
    uniform: Callable[[float, float], float] = random.uniform,
) -> T:
    for n in range(max_retries + 1):
        try:
            return call()
        except ApiError as e:
            if not e.retryable or n == max_retries:
                raise
            if e.retry_after is not None:
                delay = e.retry_after
            else:
                delay = uniform(0, min(max_delay, base_delay * 2**n))
            if delay > max_delay:
                raise
            sleep(delay)
    raise AssertionError("unreachable")


def check_cooldown(last_at: float | None, now: float, cooldown_sec: float) -> None:
    if last_at is None:
        return
    remaining = cooldown_sec - (now - last_at)
    if remaining > 0:
        raise RateLimitExceeded("cooldown", remaining)


class GeminiQuota:
    def __init__(
        self,
        rpm_limit: int,
        daily_limit: int,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(PACIFIC),
    ):
        self._rpm_limit = rpm_limit
        self._daily_limit = daily_limit
        self._monotonic = monotonic
        self._now = now
        self._lock = threading.Lock()
        self._recent: deque[float] = deque()
        self._day = None
        self._day_count = 0

    def acquire(self) -> None:
        with self._lock:
            t = self._monotonic()
            while self._recent and t - self._recent[0] >= 60:
                self._recent.popleft()
            if len(self._recent) >= self._rpm_limit:
                raise RateLimitExceeded("rpm", 60 - (t - self._recent[0]))

            now = self._now().astimezone(PACIFIC)
            if now.date() != self._day:
                self._day, self._day_count = now.date(), 0
            if self._day_count >= self._daily_limit:
                midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), PACIFIC)
                # timestamp()로 빼야 서머타임 바뀌는 날에도 정확하다
                raise RateLimitExceeded("daily", midnight.timestamp() - now.timestamp())

            self._recent.append(t)
            self._day_count += 1
