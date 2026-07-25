"""Thread-safe validated paper-trading execution records.

The engine performs deterministic local execution at a supplied price and keeps
an insertion-ordered in-memory history. ``PaperTrade`` records are immutable so
history snapshots cannot be corrupted by callers.

The legacy ``execute(symbol, side, quantity, price)`` and ``history()`` APIs are
preserved. Optional clock injection and bounded history are additive.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from math import fsum, isfinite
from numbers import Real
from threading import RLock
from typing import Callable, TypeAlias

Clock: TypeAlias = Callable[[], datetime]

_MAX_SYMBOL_LENGTH = 100


class PaperTradeSide(str, Enum):
    """Supported paper-trade directions."""

    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class PaperTrade:
    """Immutable simulated execution record."""

    symbol: str
    side: str
    quantity: float
    entry_price: float
    timestamp: datetime

    @property
    def notional_value(self) -> float:
        """Return quantity multiplied by entry price."""

        value = self.quantity * self.entry_price

        if not isfinite(value):
            raise ValueError(
                "trade notional must be finite."
            )

        return float(value)

    @property
    def is_buy(self) -> bool:
        """Return whether the record represents a BUY."""

        return self.side == PaperTradeSide.BUY.value

    @property
    def is_sell(self) -> bool:
        """Return whether the record represents a SELL."""

        return self.side == PaperTradeSide.SELL.value


class PaperTradingEngine:
    """Execute validated local paper trades and retain their history."""

    __slots__ = (
        "_clock",
        "_lock",
        "_trades",
    )

    def __init__(
        self,
        *,
        clock: Clock | None = None,
        max_history: int | None = None,
    ) -> None:
        if clock is not None and not callable(clock):
            raise TypeError(
                "clock must be callable."
            )

        normalized_max_history = (
            self._validate_max_history(
                max_history
            )
        )

        self._clock = (
            clock
            if clock is not None
            else _utc_now
        )
        self._lock = RLock()
        self._trades: deque[
            PaperTrade
        ] = deque(
            maxlen=normalized_max_history,
        )

    @staticmethod
    def _validate_max_history(
        max_history: object | None,
    ) -> int | None:
        if max_history is None:
            return None

        if (
            isinstance(max_history, bool)
            or not isinstance(max_history, int)
        ):
            raise TypeError(
                "max_history must be an integer or None."
            )

        if max_history <= 0:
            raise ValueError(
                "max_history must be greater than zero."
            )

        return max_history

    @staticmethod
    def _validate_symbol(
        symbol: object,
    ) -> str:
        if not isinstance(symbol, str):
            raise TypeError(
                "symbol must be a string."
            )

        normalized = symbol.strip()

        if not normalized:
            raise ValueError(
                "symbol cannot be empty."
            )

        if len(normalized) > _MAX_SYMBOL_LENGTH:
            raise ValueError(
                "symbol must not exceed "
                f"{_MAX_SYMBOL_LENGTH} characters."
            )

        return normalized

    @staticmethod
    def _validate_side(
        side: PaperTradeSide | str,
    ) -> str:
        if isinstance(side, PaperTradeSide):
            return side.value

        if not isinstance(side, str):
            raise TypeError(
                "side must be a string."
            )

        normalized = side.strip().lower()

        if normalized not in {
            PaperTradeSide.BUY.value,
            PaperTradeSide.SELL.value,
        }:
            raise ValueError(
                "side must be 'buy' or 'sell'."
            )

        return normalized

    @staticmethod
    def _validate_positive_number(
        value: object,
        field_name: str,
    ) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
        ):
            raise TypeError(
                f"{field_name} must be a number."
            )

        normalized = float(value)

        if not isfinite(normalized):
            raise ValueError(
                f"{field_name} must be finite."
            )

        if normalized <= 0.0:
            raise ValueError(
                f"{field_name} must be greater than zero."
            )

        return normalized

    @staticmethod
    def _validate_timestamp(
        timestamp: object,
    ) -> datetime:
        if not isinstance(timestamp, datetime):
            raise TypeError(
                "timestamp must be a datetime."
            )

        if (
            timestamp.tzinfo is None
            or timestamp.utcoffset() is None
        ):
            raise ValueError(
                "timestamp must be timezone-aware."
            )

        return timestamp.astimezone(UTC)

    @staticmethod
    def _validate_limit(
        limit: object,
    ) -> int:
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
        ):
            raise TypeError(
                "limit must be an integer."
            )

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        return limit

    def _current_time(self) -> datetime:
        return self._validate_timestamp(
            self._clock()
        )

    def execute(
        self,
        symbol: str,
        side: PaperTradeSide | str,
        quantity: float,
        price: float,
        *,
        timestamp: datetime | None = None,
    ) -> PaperTrade:
        """Execute and store one validated simulated trade."""

        validated_symbol = self._validate_symbol(
            symbol
        )
        validated_side = self._validate_side(
            side
        )
        validated_quantity = (
            self._validate_positive_number(
                quantity,
                "quantity",
            )
        )
        validated_price = (
            self._validate_positive_number(
                price,
                "price",
            )
        )
        validated_timestamp = (
            self._current_time()
            if timestamp is None
            else self._validate_timestamp(
                timestamp
            )
        )

        trade = PaperTrade(
            symbol=validated_symbol,
            side=validated_side,
            quantity=validated_quantity,
            entry_price=validated_price,
            timestamp=validated_timestamp,
        )

        # Detect multiplication overflow before mutating history.
        _ = trade.notional_value

        with self._lock:
            self._trades.append(trade)

        return trade

    def history(self) -> list[PaperTrade]:
        """Return an independent oldest-to-newest list snapshot."""

        with self._lock:
            return list(self._trades)

    def snapshot(self) -> tuple[PaperTrade, ...]:
        """Return an immutable oldest-to-newest container snapshot."""

        with self._lock:
            return tuple(self._trades)

    def latest(self) -> PaperTrade | None:
        """Return the newest trade, or ``None`` when empty."""

        with self._lock:
            if not self._trades:
                return None

            return self._trades[-1]

    def recent(
        self,
        limit: int,
    ) -> list[PaperTrade]:
        """Return up to ``limit`` newest trades in execution order."""

        normalized_limit = self._validate_limit(
            limit
        )

        with self._lock:
            if normalized_limit >= len(
                self._trades
            ):
                return list(self._trades)

            trades = list(self._trades)

        return trades[-normalized_limit:]

    def for_symbol(
        self,
        symbol: str,
    ) -> list[PaperTrade]:
        """Return trades matching a normalized symbol exactly."""

        normalized_symbol = self._validate_symbol(
            symbol
        )

        with self._lock:
            return [
                trade
                for trade in self._trades
                if trade.symbol == normalized_symbol
            ]

    def by_side(
        self,
        side: PaperTradeSide | str,
    ) -> list[PaperTrade]:
        """Return trades matching one normalized side."""

        normalized_side = self._validate_side(
            side
        )

        with self._lock:
            return [
                trade
                for trade in self._trades
                if trade.side == normalized_side
            ]

    def total_quantity(
        self,
        *,
        side: PaperTradeSide | str | None = None,
    ) -> float:
        """Return finite aggregate quantity, optionally filtered by side."""

        normalized_side = (
            None
            if side is None
            else self._validate_side(side)
        )

        with self._lock:
            values = tuple(
                trade.quantity
                for trade in self._trades
                if (
                    normalized_side is None
                    or trade.side == normalized_side
                )
            )

        return _finite_sum(
            values,
            "total quantity",
        )

    def total_notional(
        self,
        *,
        side: PaperTradeSide | str | None = None,
    ) -> float:
        """Return finite aggregate execution notional."""

        normalized_side = (
            None
            if side is None
            else self._validate_side(side)
        )

        with self._lock:
            values = tuple(
                trade.notional_value
                for trade in self._trades
                if (
                    normalized_side is None
                    or trade.side == normalized_side
                )
            )

        return _finite_sum(
            values,
            "total notional",
        )

    def clear(self) -> None:
        """Remove every stored paper trade."""

        with self._lock:
            self._trades.clear()

    @property
    def max_history(self) -> int | None:
        """Return the fixed history bound, or ``None`` when unbounded."""

        return self._trades.maxlen

    @property
    def is_full(self) -> bool:
        """Return whether a bounded history is currently at capacity."""

        with self._lock:
            return bool(
                self._trades.maxlen is not None
                and len(self._trades)
                == self._trades.maxlen
            )

    def __len__(self) -> int:
        with self._lock:
            return len(self._trades)

    def __bool__(self) -> bool:
        with self._lock:
            return bool(self._trades)

    def __iter__(self) -> Iterator[PaperTrade]:
        return iter(self.snapshot())


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _finite_sum(
    values: tuple[float, ...],
    name: str,
) -> float:
    try:
        result = fsum(values)
    except OverflowError as error:
        raise ValueError(
            f"{name} must be finite."
        ) from error

    if not isfinite(result):
        raise ValueError(
            f"{name} must be finite."
        )

    return float(result)


__all__ = (
    "PaperTrade",
    "PaperTradeSide",
    "PaperTradingEngine",
)