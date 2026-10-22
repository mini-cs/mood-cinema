from datetime import datetime

import pytest

from core.models import ApiError, RateLimitExceeded
from core.rate_limit import PACIFIC, GeminiQuota, check_cooldown, parse_retry_after, with_backoff


def _flaky(errors, result="ok"):
    """errors를 하나씩 던지고, 다 던지면 result를 돌려주는 가짜 호출."""
    calls = []

    def call():
        calls.append(1)
        if len(calls) <= len(errors):
            raise errors[len(calls) - 1]
        return result

    return call, calls


def _err(status, retry_after=None):
    return ApiError("boom", status=status, retry_after=retry_after, retryable=status in (429, 500, 502, 503, 504))


def test_retries_retryable_then_succeeds():
    sleeps = []
    call, _ = _flaky([_err(429), _err(429)])
    assert with_backoff(call, sleep=sleeps.append, uniform=lambda lo, hi: hi) == "ok"
    assert len(sleeps) == 2


def test_no_retry_when_not_retryable():
    sleeps = []
    call, calls = _flaky([_err(400)])
    with pytest.raises(ApiError):
        with_backoff(call, sleep=sleeps.append)
    assert len(calls) == 1
    assert sleeps == []


def test_gives_up_after_max_retries():
    call, calls = _flaky([_err(503)] * 10)
    with pytest.raises(ApiError):
        with_backoff(call, sleep=lambda s: None)
    assert len(calls) == 4


@pytest.mark.parametrize("base_delay,expected", [(1, [1, 2, 4]), (8, [8, 16, 20])])
def test_backoff_full_jitter_with_cap(base_delay, expected):
    sleeps = []
    call, _ = _flaky([_err(503)] * 10)
    with pytest.raises(ApiError):
        with_backoff(call, base_delay=base_delay, sleep=sleeps.append, uniform=lambda lo, hi: hi)
    assert sleeps == expected


def test_retry_after_is_used():
    sleeps = []
    call, _ = _flaky([_err(429, retry_after=3)])
    assert with_backoff(call, sleep=sleeps.append) == "ok"
    assert sleeps == [3]


def test_retry_after_over_cap_fails_fast():
    sleeps = []
    call, calls = _flaky([_err(429, retry_after=30)])
    with pytest.raises(ApiError):
        with_backoff(call, sleep=sleeps.append)
    assert len(calls) == 1
    assert sleeps == []


@pytest.mark.parametrize(
    "raw,expected",
    [("5", 5.0), ("0", 0.0), ("-1", None), ("", None), (None, None), ("Wed, 21 Oct 2026 07:28:00 GMT", None)],
)
def test_parse_retry_after(raw, expected):
    assert parse_retry_after(raw) == expected


def test_cooldown():
    with pytest.raises(RateLimitExceeded) as e:
        check_cooldown(100, 105, 10)
    assert (e.value.reason, e.value.retry_after_sec) == ("cooldown", 5)
    check_cooldown(100, 110, 10)
    check_cooldown(None, 105, 10)


class FakeClock:
    def __init__(self, t=0.0, now=datetime(2026, 10, 22, 12, 0, tzinfo=PACIFIC)):
        self.t = t
        self.now = now


def _quota(rpm, daily, clock):
    return GeminiQuota(rpm, daily, monotonic=lambda: clock.t, now=lambda: clock.now)


def test_quota_rpm_sliding_window():
    clock = FakeClock()
    q = _quota(2, 100, clock)
    q.acquire()
    clock.t = 1
    q.acquire()
    clock.t = 2
    with pytest.raises(RateLimitExceeded) as e:
        q.acquire()
    assert (e.value.reason, e.value.retry_after_sec) == ("rpm", 58)
    clock.t = 60.5
    q.acquire()


def test_quota_daily_resets_at_pacific_midnight():
    clock = FakeClock(now=datetime(2026, 10, 22, 23, 59, 0, tzinfo=PACIFIC))
    q = _quota(100, 1, clock)
    q.acquire()
    with pytest.raises(RateLimitExceeded) as e:
        q.acquire()
    assert (e.value.reason, e.value.retry_after_sec) == ("daily", 60)
    clock.now = datetime(2026, 10, 23, 0, 0, 1, tzinfo=PACIFIC)
    q.acquire()


def test_rejected_call_is_not_recorded():
    clock = FakeClock()
    q = _quota(2, 1, clock)
    q.acquire()
    with pytest.raises(RateLimitExceeded):
        q.acquire()
    clock.now = datetime(2026, 10, 23, 12, 0, tzinfo=PACIFIC)
    clock.t += 1
    q.acquire()
