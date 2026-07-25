"""Thread-safe validated execution-position tracking.

``Position`` remains a mutable transport model for compatibility with exchange
adapters and portfolio components. ``PositionManager`` stores and returns
defensive copies so external mutation cannot corrupt internal state.

PnL convention:

- BUY: ``(current_price - entry_price) * size``
- SELL: ``(entry_price - current_price) * size``

Leverage is tracked as position metadata and is used for margin calculations;
it is not multiplied into PnL because ``size`` already represents position
quantity.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import fsum, isfinite
from numbers import Real
from threading import RLock

_MAX_SYMBOL_LENGTH = 100
_VALID_SIDES = frozenset({"BUY", "SELL"})


@dataclass(slots=True)
class Position:
    """Mutable transport snapshot for one execution position."""

    symbol: str
    side: str
    size: float
    entry_price: float
    current_price: float | None = None
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    leverage: float = 1.0
    stop_loss: float | None = None
    take_profit: float | None = None
    opened_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    @property
    def mark_price(self) -> float:
        """Return current price when available, otherwise entry price."""

        if self.current_price is None:
            return float(self.entry_price)

        return float(self.current_price)

    @property
    def notional_value(self) -> float:
        """Return absolute position notional at the mark price."""

        return float(
            abs(self.size * self.mark_price)
        )

    @property
    def signed_notional(self) -> float:
        """Return positive BUY notional and negative SELL notional."""

        direction = 1.0 if self.side == "BUY" else -1.0
        return float(
            direction * self.notional_value
        )

    @property
    def margin_used(self) -> float:
        """Return notional divided by leverage."""

        return float(
            self.notional_value / self.leverage
        )


class PositionManager:
    """Thread-safe in-memory manager for open execution positions."""

    __slots__ = (
        "_lock",
        "positions",
    )

    def __init__(self) -> None:
        self.positions: dict[
            str,
            Position,
        ] = {}
        self._lock = RLock()

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
        side: object,
    ) -> str:
        if not isinstance(side, str):
            raise TypeError(
                "side must be a string."
            )

        normalized = side.strip().upper()

        if normalized not in _VALID_SIDES:
            raise ValueError(
                "side must be 'BUY' or 'SELL'."
            )

        return normalized

    @staticmethod
    def _validate_positive_finite(
        value: object,
        name: str,
    ) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
        ):
            raise TypeError(
                f"{name} must be a number."
            )

        normalized = float(value)

        if not isfinite(normalized):
            raise ValueError(
                f"{name} must be finite."
            )

        if normalized <= 0.0:
            raise ValueError(
                f"{name} must be greater than zero."
            )

        return normalized

    @staticmethod
    def _validate_finite(
        value: object,
        name: str,
    ) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
        ):
            raise TypeError(
                f"{name} must be a number."
            )

        normalized = float(value)

        if not isfinite(normalized):
            raise ValueError(
                f"{name} must be finite."
            )

        return normalized

    @staticmethod
    def _validate_timestamp(
        opened_at: object,
    ) -> datetime:
        if not isinstance(opened_at, datetime):
            raise TypeError(
                "opened_at must be a datetime."
            )

        if (
            opened_at.tzinfo is None
            or opened_at.utcoffset() is None
        ):
            raise ValueError(
                "opened_at must be timezone-aware."
            )

        return opened_at.astimezone(UTC)

    @classmethod
    def _validate_position(
        cls,
        position: object,
    ) -> Position:
        if not isinstance(position, Position):
            raise TypeError(
                "position must be a Position."
            )

        symbol = cls._validate_symbol(
            position.symbol
        )
        side = cls._validate_side(
            position.side
        )
        size = cls._validate_positive_finite(
            position.size,
            "size",
        )
        entry_price = cls._validate_positive_finite(
            position.entry_price,
            "entry_price",
        )
        leverage = cls._validate_positive_finite(
            position.leverage,
            "leverage",
        )

        current_price = None
        if position.current_price is not None:
            current_price = cls._validate_positive_finite(
                position.current_price,
                "current_price",
            )

        stop_loss = None
        if position.stop_loss is not None:
            stop_loss = cls._validate_positive_finite(
                position.stop_loss,
                "stop_loss",
            )

        take_profit = None
        if position.take_profit is not None:
            take_profit = cls._validate_positive_finite(
                position.take_profit,
                "take_profit",
            )

        unrealized_pnl = cls._validate_finite(
            position.unrealized_pnl,
            "unrealized_pnl",
        )
        realized_pnl = cls._validate_finite(
            position.realized_pnl,
            "realized_pnl",
        )
        opened_at = cls._validate_timestamp(
            position.opened_at
        )

        cls._ensure_finite_product(
            size,
            entry_price,
            "position notional",
        )
        cls._ensure_finite_quotient(
            size * entry_price,
            leverage,
            "position margin",
        )

        return Position(
            symbol=symbol,
            side=side,
            size=size,
            entry_price=entry_price,
            current_price=current_price,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=realized_pnl,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit,
            opened_at=opened_at,
        )

    @staticmethod
    def _ensure_finite_product(
        left: float,
        right: float,
        name: str,
    ) -> float:
        result = left * right

        if not isfinite(result):
            raise ValueError(
                f"{name} must be finite."
            )

        return float(result)

    @staticmethod
    def _ensure_finite_quotient(
        numerator: float,
        denominator: float,
        name: str,
    ) -> float:
        result = numerator / denominator

        if not isfinite(result):
            raise ValueError(
                f"{name} must be finite."
            )

        return float(result)

    @classmethod
    def _calculate_unrealized_pnl(
        cls,
        position: Position,
        price: float,
    ) -> float:
        if position.side == "BUY":
            difference = (
                price - position.entry_price
            )
        else:
            difference = (
                position.entry_price - price
            )

        pnl = difference * position.size

        if not isfinite(pnl):
            raise ValueError(
                "unrealized_pnl must be finite."
            )

        return float(pnl)

    @classmethod
    def _normalize_price_updates(
        cls,
        prices: object,
    ) -> dict[str, float]:
        if not isinstance(prices, Mapping):
            raise TypeError(
                "prices must be a mapping."
            )

        normalized: dict[str, float] = {}

        for symbol, price in prices.items():
            normalized_symbol = cls._validate_symbol(
                symbol
            )

            if normalized_symbol in normalized:
                raise ValueError(
                    "Duplicate symbol in prices."
                )

            normalized[
                normalized_symbol
            ] = cls._validate_positive_finite(
                price,
                "price",
            )

        return normalized

    def open_position(
        self,
        position: Position,
    ) -> None:
        """Open one validated position.

        A symbol may have at most one open position in this manager.
        """

        normalized = self._validate_position(
            position
        )

        with self._lock:
            if normalized.symbol in self.positions:
                raise ValueError(
                    "Position already exists."
                )

            self.positions[
                normalized.symbol
            ] = deepcopy(normalized)

    def open_many(
        self,
        positions: object,
    ) -> int:
        """Atomically open multiple positions.

        Every item and duplicate condition is validated before state changes.

        Returns:
            Number of positions opened.
        """

        if (
            isinstance(
                positions,
                (
                    str,
                    bytes,
                    bytearray,
                ),
            )
            or not hasattr(positions, "__iter__")
        ):
            raise TypeError(
                "positions must be an iterable "
                "of Position objects."
            )

        normalized = tuple(
            self._validate_position(position)
            for position in positions
        )
        symbols = tuple(
            position.symbol
            for position in normalized
        )

        if len(symbols) != len(set(symbols)):
            raise ValueError(
                "Duplicate symbol in positions."
            )

        with self._lock:
            if any(
                symbol in self.positions
                for symbol in symbols
            ):
                raise ValueError(
                    "Position already exists."
                )

            for position in normalized:
                self.positions[
                    position.symbol
                ] = deepcopy(position)

        return len(normalized)

    def close_position(
        self,
        symbol: str,
    ) -> Position:
        """Close and return a defensive copy of one position."""

        normalized_symbol = self._validate_symbol(
            symbol
        )

        with self._lock:
            try:
                position = self.positions.pop(
                    normalized_symbol
                )
            except KeyError as error:
                raise KeyError(
                    "Unknown position: "
                    f"{normalized_symbol}"
                ) from error

            return deepcopy(position)

    def get_position(
        self,
        symbol: str,
    ) -> Position | None:
        """Return a defensive copy, or ``None`` when missing."""

        normalized_symbol = self._validate_symbol(
            symbol
        )

        with self._lock:
            position = self.positions.get(
                normalized_symbol
            )

            if position is None:
                return None

            return deepcopy(position)

    def require_position(
        self,
        symbol: str,
    ) -> Position:
        """Return one position or raise ``KeyError`` when missing."""

        normalized_symbol = self._validate_symbol(
            symbol
        )

        with self._lock:
            try:
                return deepcopy(
                    self.positions[
                        normalized_symbol
                    ]
                )
            except KeyError as error:
                raise KeyError(
                    "Unknown position: "
                    f"{normalized_symbol}"
                ) from error

    def list_positions(
        self,
    ) -> list[Position]:
        """Return insertion-ordered defensive copies."""

        with self._lock:
            return deepcopy(
                list(
                    self.positions.values()
                )
            )

    def snapshot(
        self,
    ) -> tuple[Position, ...]:
        """Return an independent tuple snapshot."""

        return tuple(
            self.list_positions()
        )

    def positions_by_side(
        self,
        side: str,
    ) -> list[Position]:
        """Return defensive copies for one normalized side."""

        normalized_side = self._validate_side(
            side
        )

        with self._lock:
            return deepcopy(
                [
                    position
                    for position
                    in self.positions.values()
                    if (
                        position.side
                        == normalized_side
                    )
                ]
            )

    def update_price(
        self,
        symbol: str,
        price: float,
    ) -> None:
        """Update one mark price and recalculate unrealized PnL."""

        normalized_symbol = self._validate_symbol(
            symbol
        )
        normalized_price = (
            self._validate_positive_finite(
                price,
                "price",
            )
        )

        with self._lock:
            position = self.positions.get(
                normalized_symbol
            )

            if position is None:
                raise KeyError(
                    "Unknown position: "
                    f"{normalized_symbol}"
                )

            pnl = self._calculate_unrealized_pnl(
                position,
                normalized_price,
            )
            self._ensure_finite_product(
                position.size,
                normalized_price,
                "position notional",
            )

            position.current_price = normalized_price
            position.unrealized_pnl = pnl

    def update_prices(
        self,
        prices: Mapping[str, float],
    ) -> int:
        """Atomically update multiple mark prices and PnL values."""

        normalized = (
            self._normalize_price_updates(
                prices
            )
        )

        with self._lock:
            missing = [
                symbol
                for symbol in normalized
                if symbol not in self.positions
            ]

            if missing:
                raise KeyError(
                    "Unknown position: "
                    f"{missing[0]}"
                )

            calculated: dict[
                str,
                tuple[float, float],
            ] = {}

            for symbol, price in normalized.items():
                position = self.positions[symbol]
                pnl = self._calculate_unrealized_pnl(
                    position,
                    price,
                )
                self._ensure_finite_product(
                    position.size,
                    price,
                    "position notional",
                )
                calculated[symbol] = (
                    price,
                    pnl,
                )

            for symbol, (
                price,
                pnl,
            ) in calculated.items():
                position = self.positions[symbol]
                position.current_price = price
                position.unrealized_pnl = pnl

        return len(normalized)

    def update_risk_levels(
        self,
        symbol: str,
        *,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> None:
        """Replace optional stop-loss and take-profit levels."""

        normalized_symbol = self._validate_symbol(
            symbol
        )

        normalized_stop = None
        if stop_loss is not None:
            normalized_stop = (
                self._validate_positive_finite(
                    stop_loss,
                    "stop_loss",
                )
            )

        normalized_target = None
        if take_profit is not None:
            normalized_target = (
                self._validate_positive_finite(
                    take_profit,
                    "take_profit",
                )
            )

        with self._lock:
            position = self.positions.get(
                normalized_symbol
            )

            if position is None:
                raise KeyError(
                    "Unknown position: "
                    f"{normalized_symbol}"
                )

            position.stop_loss = normalized_stop
            position.take_profit = normalized_target

    def exists(
        self,
        symbol: str,
    ) -> bool:
        """Return whether a normalized symbol has an open position."""

        normalized_symbol = self._validate_symbol(
            symbol
        )

        with self._lock:
            return (
                normalized_symbol
                in self.positions
            )

    def total_unrealized_pnl(
        self,
    ) -> float:
        """Return finite aggregate unrealized PnL."""

        with self._lock:
            values = tuple(
                position.unrealized_pnl
                for position
                in self.positions.values()
            )

        return _finite_sum(
            values,
            "total unrealized_pnl",
        )

    def total_realized_pnl(
        self,
    ) -> float:
        """Return finite aggregate realized PnL."""

        with self._lock:
            values = tuple(
                position.realized_pnl
                for position
                in self.positions.values()
            )

        return _finite_sum(
            values,
            "total realized_pnl",
        )

    def gross_exposure(
        self,
    ) -> float:
        """Return finite sum of absolute marked notionals."""

        with self._lock:
            values = tuple(
                position.notional_value
                for position
                in self.positions.values()
            )

        return _finite_sum(
            values,
            "gross exposure",
        )

    def net_exposure(
        self,
    ) -> float:
        """Return signed BUY-minus-SELL marked notional."""

        with self._lock:
            values = tuple(
                position.signed_notional
                for position
                in self.positions.values()
            )

        return _finite_sum(
            values,
            "net exposure",
        )

    def total_margin_used(
        self,
    ) -> float:
        """Return finite aggregate marked margin usage."""

        with self._lock:
            values = tuple(
                position.margin_used
                for position
                in self.positions.values()
            )

        return _finite_sum(
            values,
            "total margin",
        )

    def clear(
        self,
    ) -> None:
        """Remove every open position."""

        with self._lock:
            self.positions.clear()

    def count(
        self,
    ) -> int:
        """Return the number of open positions."""

        return len(self)

    def __len__(
        self,
    ) -> int:
        with self._lock:
            return len(self.positions)

    def __bool__(
        self,
    ) -> bool:
        with self._lock:
            return bool(self.positions)

    def __iter__(
        self,
    ) -> Iterator[Position]:
        return iter(self.snapshot())


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
    "Position",
    "PositionManager",
)