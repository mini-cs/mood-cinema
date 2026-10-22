import threading
import time
from collections.abc import Callable, Hashable
from typing import Any, TypeVar

T = TypeVar("T")


class TTLCache:
    def __init__(self, *, max_entries: int = 1024, clock: Callable[[], float] = time.monotonic):
        self._max_entries = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._data: dict[Hashable, tuple[float, Any]] = {}  # 키 → (만료 시각, 값). dict는 넣은 순서를 기억한다

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def get_or_set(self, key: Hashable, ttl: float, factory: Callable[[], T]) -> T:
        with self._lock:
            entry = self._data.get(key)
            if entry is not None and self._clock() < entry[0]:
                return entry[1]
        # factory(외부 API 호출)는 락 밖에서 부른다. 동시에 같은 키가 두 번 계산될 수 있지만 허용한다
        value = factory()
        with self._lock:
            now = self._clock()
            self._data.pop(key, None)  # 다시 넣으면 "가장 최근에 넣은 항목"이 된다
            self._data[key] = (now + ttl, value)
            if len(self._data) > self._max_entries:
                for k in [k for k, (expires, _) in self._data.items() if expires <= now]:
                    del self._data[k]
            while len(self._data) > self._max_entries:
                del self._data[next(iter(self._data))]
        return value
