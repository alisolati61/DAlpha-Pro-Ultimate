"""Validated market snapshot shared across the data subsystem."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


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
    minimum: float | None = None,
    strictly_positive: bool = False,
) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be numeric.")

    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
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


@dataclass(frozen=True, slots=True)
class MarketData:
    """Immutable, validated top-of-book market snapshot.

    ``spread`` is always derived from ``ask - bid``. Any caller-provided
    spread value is ignored so inconsistent snapshots cannot enter the data
    pipeline.
    """

    symbol: str
    exchange: str
    timeframe: str
    price: float
    bid: float
    ask: float
    volume: float
    timestamp: datetime
    spread: float = 0.0

    def __post_init__(self) -> None:
        symbol = _required_text(
            self.symbol,
            field_name="symbol",
        )
        exchange = _required_text(
            self.exchange,
            field_name="exchange",
        )
        timeframe = _required_text(
            self.timeframe,
            field_name="timeframe",
        )
        price = _finite_float(
            self.price,
            field_name="price",
            strictly_positive=True,
        )
        bid = _finite_float(
            self.bid,
            field_name="bid",
            minimum=0.0,
        )
        ask = _finite_float(
            self.ask,
            field_name="ask",
            minimum=0.0,
        )
        volume = _finite_float(
            self.volume,
            field_name="volume",
            minimum=0.0,
        )
        timestamp = _utc_timestamp(self.timestamp)

        if ask < bid:
            raise ValueError(
                "ask must be greater than or equal to bid."
            )

        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "exchange", exchange)
        object.__setattr__(self, "timeframe", timeframe)
        object.__setattr__(self, "price", price)
        object.__setattr__(self, "bid", bid)
        object.__setattr__(self, "ask", ask)
        object.__setattr__(self, "volume", volume)
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "spread", ask - bid)

    @property
    def mid_price(self) -> float:
        """Return the top-of-book midpoint."""

        return (self.bid + self.ask) / 2.0

    @property
    def spread_bps(self) -> float:
        """Return spread as basis points of the midpoint."""

        midpoint = self.mid_price

        if midpoint == 0.0:
            return 0.0

        return self.spread / midpoint * 10_000.0


__all__ = ("MarketData",)