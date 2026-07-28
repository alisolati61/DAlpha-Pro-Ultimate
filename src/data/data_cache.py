"""Deterministic, thread-safe in-memory cache."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Any


@dataclass(frozen=True, slots=True)
class CacheItem:
    value: Any
    expires_at: float


class DataCache:
    """Generic local cache with expiration at ``now >= expires_at``."""

    def __init__(
        self,
        ttl_seconds: float = 60,
        *,
        timer: Callable[[], float] = monotonic,
    ) -> None:
        if (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, (int, float))
            or not math.isfinite(float(ttl_seconds))
            or float(ttl_seconds) <= 0
        ):
            raise ValueError("ttl_seconds must be finite and positive.")
        if not callable(timer):
            raise TypeError("timer must be callable.")

        self.ttl_seconds = float(ttl_seconds)
        self._timer = timer
        self._cache: dict[str, CacheItem] = {}
        self._lock = RLock()

    def set(self, key: str, value: Any) -> None:
        normalized_key = self._key(key)
        expires_at = self._now() + self.ttl_seconds
        with self._lock:
            self._cache[normalized_key] = CacheItem(value, expires_at)

    def get(self, key: str) -> Any | None:
        normalized_key = self._key(key)
        now = self._now()
        with self._lock:
            item = self._cache.get(normalized_key)
            if item is None:
                return None
            if now >= item.expires_at:
                del self._cache[normalized_key]
                return None
            return item.value

    def remove(self, key: str) -> None:
        normalized_key = self._key(key)
        with self._lock:
            self._cache.pop(normalized_key, None)

    def purge_expired(self) -> int:
        now = self._now()
        with self._lock:
            expired = [
                key
                for key, item in self._cache.items()
                if now >= item.expires_at
            ]
            for key in expired:
                del self._cache[key]
            return len(expired)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        self.purge_expired()
        with self._lock:
            return len(self._cache)

    @staticmethod
    def _key(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("cache key must be a non-empty string.")
        return value.strip()

    def _now(self) -> float:
        value = self._timer()
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise ValueError("timer must return a finite number.")
        return float(value)

    def _snapshot_state(self) -> dict[str, CacheItem]:
        with self._lock:
            return dict(self._cache)

    def _restore_state(
        self,
        state: dict[str, CacheItem],
    ) -> None:
        with self._lock:
            self._cache = dict(state)


__all__ = (
    "CacheItem",
    "DataCache",
)
