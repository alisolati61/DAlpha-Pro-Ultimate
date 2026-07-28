"""Validated, thread-safe processing for live market ticks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Any


def _required_symbol(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("symbol must be a string.")

    normalized = value.strip()

    if not normalized:
        raise ValueError("symbol cannot be empty.")

    return normalized


def _finite_float(
    value: Any,
    *,
    field_name: str,
    strictly_positive: bool = False,
    minimum: float | None = None,
) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be numeric.")

    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be numeric.") from exc

    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")

    if strictly_positive and normalized <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    if minimum is not None and normalized < minimum:
        raise ValueError(
            f"{field_name} must be greater than or equal to {minimum}."
        )

    return normalized


def _utc_timestamp(value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("timestamp must be a datetime.")

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


@dataclass(slots=True)
class Tick:
    """One normalized market tick.

    The object intentionally remains mutable for backward compatibility with
    the existing project contract. ``TickProcessor`` itself never mutates a
    stored tick after publication.
    """

    symbol: str
    price: float
    volume: float
    timestamp: datetime

    def __post_init__(self) -> None:
        self.symbol = _required_symbol(self.symbol)
        self.price = _finite_float(
            self.price,
            field_name="price",
            strictly_positive=True,
        )
        self.volume = _finite_float(
            self.volume,
            field_name="volume",
            minimum=0.0,
        )
        self.timestamp = _utc_timestamp(self.timestamp)


class TickProcessor:
    """Validate ticks, retain the latest tick per symbol, and count them."""

    def __init__(self) -> None:
        self._latest: dict[str, Tick] = {}
        self._count = 0
        self._lock = RLock()

    def process(
        self,
        symbol: str,
        price: float,
        volume: float,
        timestamp: datetime | None = None,
    ) -> Tick:
        """Validate and atomically publish one tick.

        Invalid input raises before processor state changes. The existing
        behavior is preserved: each accepted tick replaces the previous latest
        tick for its symbol, regardless of timestamp ordering.
        """

        tick = Tick(
            symbol=symbol,
            price=price,
            volume=volume,
            timestamp=(
                datetime.now(UTC)
                if timestamp is None
                else timestamp
            ),
        )

        with self._lock:
            self._latest[tick.symbol] = tick
            self._count += 1

        return tick

    def latest(
        self,
        symbol: str,
    ) -> Tick | None:
        """Return the latest accepted tick for a normalized symbol."""

        normalized_symbol = _required_symbol(symbol)

        with self._lock:
            return self._latest.get(normalized_symbol)

    @property
    def processed_ticks(self) -> int:
        """Return the number of accepted ticks since the last clear."""

        with self._lock:
            return self._count

    def clear(self) -> None:
        """Atomically clear latest ticks and reset the accepted-tick count."""

        with self._lock:
            self._latest.clear()
            self._count = 0

    def _snapshot_state(self) -> tuple[dict[str, Tick], int]:
        with self._lock:
            return (dict(self._latest), self._count)

    def _restore_state(
        self,
        state: tuple[dict[str, Tick], int],
    ) -> None:
        with self._lock:
            self._latest = dict(state[0])
            self._count = state[1]


__all__ = (
    "Tick",
    "TickProcessor",
)
