import pytest

from core.ttl_cache import TTLCache


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class Factory:
    """호출 횟수를 세는 값 생성기."""

    def __init__(self, value="v"):
        self.value = value
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.value


def test_returns_cached_within_ttl():
    clock, f = Clock(), Factory()
    cache = TTLCache(clock=clock)
    assert cache.get_or_set("k", 60, f) == "v"
    clock.t = 59
    assert cache.get_or_set("k", 60, f) == "v"
    assert f.calls == 1


def test_recomputes_after_ttl():
    clock, f = Clock(), Factory()
    cache = TTLCache(clock=clock)
    cache.get_or_set("k", 60, f)
    clock.t = 60
    cache.get_or_set("k", 60, f)
    assert f.calls == 2


def test_exceptions_are_not_cached():
    cache = TTLCache(clock=Clock())

    def boom():
        raise ValueError("x")

    with pytest.raises(ValueError):
        cache.get_or_set("k", 60, boom)
    assert cache.get_or_set("k", 60, Factory("ok")) == "ok"
    assert len(cache) == 1


def test_evicts_expired_then_oldest():
    clock = Clock()
    cache = TTLCache(max_entries=2, clock=clock)
    b, a = Factory("b"), Factory("a")
    cache.get_or_set("b", 100, b)  # 가장 먼저 넣었지만 아직 살아 있음
    cache.get_or_set("a", 10, a)
    clock.t = 20  # a만 만료
    cache.get_or_set("c", 100, Factory("c"))
    assert len(cache) == 2
    cache.get_or_set("b", 100, b)
    assert b.calls == 1  # 만료된 a가 먼저 지워졌으므로 b는 남아 있다

    c_again = Factory("c")
    cache.get_or_set("d", 100, Factory("d"))  # 만료된 게 없으니 가장 오래된 b가 지워진다
    cache.get_or_set("c", 100, c_again)
    assert c_again.calls == 0
    cache.get_or_set("b", 100, b)
    assert b.calls == 2
