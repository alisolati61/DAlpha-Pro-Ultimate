from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass(slots=True)
class CacheItem:
    value: Any
    created_at: datetime


class DataCache:
    """
    Simple in-memory cache for market data.

    Future
    -------
    - Redis
    - Disk Cache
    - Distributed Cache
    """

    def __init__(
        self,
        ttl_seconds: int = 60,
    ) -> None:

        self.ttl = timedelta(
            seconds=ttl_seconds,
        )

        self._cache: dict[str, CacheItem] = {}

    # ---------------------------------------------

    def set(
        self,
        key: str,
        value: Any,
    ) -> None:

        self._cache[key] = CacheItem(
            value=value,
            created_at=datetime.now(UTC),
        )

    # ---------------------------------------------

    def get(
        self,
        key: str,
    ) -> Any | None:

        item = self._cache.get(key)

        if item is None:
            return None

        if datetime.now(UTC) - item.created_at > self.ttl:

            del self._cache[key]

            return None

        return item.value

    # ---------------------------------------------

    def remove(
        self,
        key: str,
    ) -> None:

        self._cache.pop(key, None)

    # ---------------------------------------------

    def clear(self) -> None:

        self._cache.clear()

    # ---------------------------------------------

    @property
    def size(self) -> int:

        return len(self._cache)