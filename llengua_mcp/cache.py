"""Cache TTL en memòria, petita i sense dependències."""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any


@dataclass
class _Entry:
    expires_at: float
    value: Any


class TTLCache:
    def __init__(self, *, max_entries: int = 512, default_ttl: int = 3600) -> None:
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        self._data: OrderedDict[str, _Entry] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any | None:
        entry = self._data.get(key)
        if entry is None:
            self.misses += 1
            return None
        if entry.expires_at < time.monotonic():
            self._data.pop(key, None)
            self.misses += 1
            return None
        self._data.move_to_end(key)
        self.hits += 1
        return entry.value

    def set(self, key: str, value: Any, *, ttl: int | None = None) -> None:
        expires_at = time.monotonic() + (ttl if ttl is not None else self.default_ttl)
        self._data[key] = _Entry(expires_at, value)
        self._data.move_to_end(key)
        while len(self._data) > self.max_entries:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()
