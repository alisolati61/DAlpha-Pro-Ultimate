"""Safe in-memory OHLCV candle aggregation from market ticks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Any

_CandleValues = tuple[
    str,
    str,
    float,
    float,
    float,
    float,
    float,
    datetime,
]


def _required_text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{field_name} cannot be empty.")

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
class Candle:
    """Mutable current OHLCV candle kept by ``CandleBuilder``."""

    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    start_time: datetime

    def __post_init__(self) -> None:
        symbol = _required_text(
            self.symbol,
            field_name="symbol",
        )
        timeframe = _required_text(
            self.timeframe,
            field_name="timeframe",
        )
        open_price = _finite_float(
            self.open,
            field_name="open",
            strictly_positive=True,
        )
        high_price = _finite_float(
            self.high,
            field_name="high",
            strictly_positive=True,
        )
        low_price = _finite_float(
            self.low,
            field_name="low",
            strictly_positive=True,
        )
        close_price = _finite_float(
            self.close,
            field_name="close",
            strictly_positive=True,
        )
        volume = _finite_float(
            self.volume,
            field_name="volume",
            minimum=0.0,
        )
        start_time = _utc_timestamp(self.start_time)

        if high_price < low_price:
            raise ValueError("high must be greater than or equal to low.")

        if not low_price <= open_price <= high_price:
            raise ValueError("open must be within the candle range.")

        if not low_price <= close_price <= high_price:
            raise ValueError("close must be within the candle range.")

        self.symbol = symbol
        self.timeframe = timeframe
        self.open = open_price
        self.high = high_price
        self.low = low_price
        self.close = close_price
        self.volume = volume
        self.start_time = start_time


class CandleBuilder:
    """Build one current candle per ``(symbol, timeframe)`` key.

    The public behavior remains intentionally simple: this class aggregates
    ticks into the current candle until that key is cleared. Timeframe rollover
    belongs to a higher-level scheduler because the existing project contract
    does not define interval parsing or completed-candle emission.
    """

    def __init__(self) -> None:
        self._current: dict[tuple[str, str], Candle] = {}
        self._lock = RLock()

    def update(
        self,
        symbol: str,
        timeframe: str,
        price: float,
        volume: float,
        timestamp: datetime | None = None,
    ) -> Candle:
        """Validate and atomically aggregate one tick."""

        normalized_symbol = _required_text(
            symbol,
            field_name="symbol",
        )
        normalized_timeframe = _required_text(
            timeframe,
            field_name="timeframe",
        )
        normalized_price = _finite_float(
            price,
            field_name="price",
            strictly_positive=True,
        )
        normalized_volume = _finite_float(
            volume,
            field_name="volume",
            minimum=0.0,
        )
        normalized_timestamp = _utc_timestamp(
            datetime.now(UTC) if timestamp is None else timestamp
        )

        key = (
            normalized_symbol,
            normalized_timeframe,
        )

        with self._lock:
            candle = self._current.get(key)

            if candle is None:
                candle = Candle(
                    symbol=normalized_symbol,
                    timeframe=normalized_timeframe,
                    open=normalized_price,
                    high=normalized_price,
                    low=normalized_price,
                    close=normalized_price,
                    volume=normalized_volume,
                    start_time=normalized_timestamp,
                )
                self._current[key] = candle
                return candle

            new_high = max(candle.high, normalized_price)
            new_low = min(candle.low, normalized_price)
            new_volume = candle.volume + normalized_volume

            if not math.isfinite(new_volume):
                raise ValueError("cumulative volume must be finite.")

            candle.high = new_high
            candle.low = new_low
            candle.close = normalized_price
            candle.volume = new_volume

            return candle

    def latest(
        self,
        symbol: str,
        timeframe: str,
    ) -> Candle | None:
        """Return the current candle for a normalized key."""

        normalized_symbol = _required_text(
            symbol,
            field_name="symbol",
        )
        normalized_timeframe = _required_text(
            timeframe,
            field_name="timeframe",
        )

        with self._lock:
            return self._current.get(
                (
                    normalized_symbol,
                    normalized_timeframe,
                )
            )

    def clear(self) -> None:
        """Remove every current candle."""

        with self._lock:
            self._current.clear()

    @property
    def size(self) -> int:
        """Return the number of active symbol/timeframe candles."""

        with self._lock:
            return len(self._current)

    def _snapshot_state(
        self,
    ) -> dict[tuple[str, str], tuple[Candle, _CandleValues]]:
        with self._lock:
            return {
                key: (
                    candle,
                    (
                        candle.symbol,
                        candle.timeframe,
                        candle.open,
                        candle.high,
                        candle.low,
                        candle.close,
                        candle.volume,
                        candle.start_time,
                    ),
                )
                for key, candle in self._current.items()
            }

    def _restore_state(
        self,
        state: dict[
            tuple[str, str],
            tuple[Candle, _CandleValues],
        ],
    ) -> None:
        with self._lock:
            restored: dict[tuple[str, str], Candle] = {}
            for key, (candle, values) in state.items():
                (
                    candle.symbol,
                    candle.timeframe,
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                    candle.volume,
                    candle.start_time,
                ) = values
                restored[key] = candle
            self._current = restored


__all__ = (
    "Candle",
    "CandleBuilder",
)
