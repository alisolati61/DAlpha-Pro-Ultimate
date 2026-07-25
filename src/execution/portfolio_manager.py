"""Thread-safe execution portfolio accounting.

The historical public contract is intentionally preserved:

- ``add_position`` stores the supplied ``Position`` object itself.
- ``get_position`` returns that same object.
- adding an existing symbol replaces the previous object.
- removing a missing symbol is safe.
- ``all_positions`` returns a new list containing the tracked objects.

These identity semantics are retained for compatibility with components that
mutate a shared live position. Callers that need isolation should use
``get_position_copy`` or ``snapshot``.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from copy import deepcopy
from math import fsum, isfinite
from numbers import Real
from threading import RLock

from src.execution.position_manager import Position

_MAX_SYMBOL_LENGTH = 100
_VALID_SIDES = frozenset({"BUY", "SELL"})


class PortfolioManager:
    """Manage account balance and live execution positions."""

    def __init__(
        self,
        balance: float = 0.0,
    ) -> None:
        self.balance = self._validate_balance(
            balance
        )
        self.positions: dict[str, Position] = {}
        self._lock = RLock()

    @staticmethod
    def _validate_balance(
        balance: object,
    ) -> float:
        if (
            isinstance(balance, bool)
            or not isinstance(balance, Real)
        ):
            raise TypeError(
                "balance must be a number."
            )

        normalized = float(balance)

        if not isfinite(normalized):
            raise ValueError(
                "balance must be finite."
            )

        if normalized < 0.0:
            raise ValueError(
                "balance cannot be negative."
            )

        return normalized

    @staticmethod
    def _validate_delta(
        amount: object,
    ) -> float:
        if (
            isinstance(amount, bool)
            or not isinstance(amount, Real)
        ):
            raise TypeError(
                "amount must be a number."
            )

        normalized = float(amount)

        if not isfinite(normalized):
            raise ValueError(
                "amount must be finite."
            )

        return normalized

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
    def _validate_position(
        position: object,
    ) -> Position:
        if not isinstance(position, Position):
            raise TypeError(
                "position must be a Position."
            )

        return position

    @staticmethod
    def _finite_number(
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

    @classmethod
    def _position_mark_price(
        cls,
        position: Position,
    ) -> float:
        source = (
            position.current_price
            if position.current_price is not None
            else position.entry_price
        )
        price = cls._finite_number(
            source,
            "position price",
        )

        if price <= 0.0:
            raise ValueError(
                "position price must be greater than zero."
            )

        return price

    @classmethod
    def _position_size(
        cls,
        position: Position,
    ) -> float:
        return cls._finite_number(
            position.size,
            "position size",
        )

    @classmethod
    def _position_side(
        cls,
        position: Position,
    ) -> str:
        if not isinstance(position.side, str):
            raise TypeError(
                "position side must be a string."
            )

        side = position.side.strip().upper()

        if side not in _VALID_SIDES:
            raise ValueError(
                "position side must be 'BUY' or 'SELL'."
            )

        return side

    @staticmethod
    def _finite_sum(
        values: Iterable[float],
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

    def set_balance(
        self,
        balance: float,
    ) -> None:
        """Replace account balance after validation."""

        normalized = self._validate_balance(
            balance
        )

        with self._lock:
            self.balance = normalized

    def get_balance(self) -> float:
        """Return the current account balance."""

        with self._lock:
            return float(self.balance)

    def adjust_balance(
        self,
        amount: float,
    ) -> float:
        """Apply a signed balance change and return the new balance."""

        normalized = self._validate_delta(
            amount
        )

        with self._lock:
            updated = self.balance + normalized

            if not isfinite(updated):
                raise ValueError(
                    "balance must be finite."
                )

            if updated < 0.0:
                raise ValueError(
                    "balance cannot be negative."
                )

            self.balance = float(updated)
            return self.balance

    def deposit(
        self,
        amount: float,
    ) -> float:
        """Increase balance by a strictly positive amount."""

        normalized = self._validate_delta(
            amount
        )

        if normalized <= 0.0:
            raise ValueError(
                "deposit amount must be greater than zero."
            )

        return self.adjust_balance(normalized)

    def withdraw(
        self,
        amount: float,
    ) -> float:
        """Decrease balance by a strictly positive available amount."""

        normalized = self._validate_delta(
            amount
        )

        if normalized <= 0.0:
            raise ValueError(
                "withdrawal amount must be greater than zero."
            )

        return self.adjust_balance(
            -normalized
        )

    def add_position(
        self,
        position: Position,
    ) -> None:
        """Insert or replace a live position by normalized symbol.

        The supplied object is stored directly to preserve the historical
        shared-identity contract.
        """

        normalized_position = (
            self._validate_position(
                position
            )
        )
        symbol = self._validate_symbol(
            normalized_position.symbol
        )

        with self._lock:
            normalized_position.symbol = symbol
            self.positions[symbol] = (
                normalized_position
            )

    def add_positions(
        self,
        positions: Iterable[Position],
    ) -> int:
        """Atomically insert or replace multiple live positions.

        Duplicate normalized symbols inside the input batch are rejected.
        Supplied objects keep their identity and are normalized only after all
        validation succeeds.
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
            or not isinstance(positions, Iterable)
        ):
            raise TypeError(
                "positions must be an iterable "
                "of Position objects."
            )

        validated: list[
            tuple[Position, str]
        ] = []

        for position in positions:
            normalized_position = (
                self._validate_position(
                    position
                )
            )
            symbol = self._validate_symbol(
                normalized_position.symbol
            )
            validated.append(
                (
                    normalized_position,
                    symbol,
                )
            )

        symbols = [
            symbol
            for _, symbol in validated
        ]

        if len(symbols) != len(set(symbols)):
            raise ValueError(
                "Duplicate symbol in positions."
            )

        with self._lock:
            for position, symbol in validated:
                position.symbol = symbol
                self.positions[symbol] = position

        return len(validated)

    def replace_positions(
        self,
        positions: Iterable[Position],
    ) -> int:
        """Atomically replace the complete live-position mapping."""

        if (
            isinstance(
                positions,
                (
                    str,
                    bytes,
                    bytearray,
                ),
            )
            or not isinstance(positions, Iterable)
        ):
            raise TypeError(
                "positions must be an iterable "
                "of Position objects."
            )

        validated: list[
            tuple[Position, str]
        ] = []

        for position in positions:
            normalized_position = (
                self._validate_position(
                    position
                )
            )
            symbol = self._validate_symbol(
                normalized_position.symbol
            )
            validated.append(
                (
                    normalized_position,
                    symbol,
                )
            )

        symbols = [
            symbol
            for _, symbol in validated
        ]

        if len(symbols) != len(set(symbols)):
            raise ValueError(
                "Duplicate symbol in positions."
            )

        replacement = {
            symbol: position
            for position, symbol in validated
        }

        with self._lock:
            for position, symbol in validated:
                position.symbol = symbol

            self.positions = replacement

        return len(validated)

    def remove_position(
        self,
        symbol: str,
    ) -> None:
        """Remove a live position; missing symbols are ignored."""

        normalized = self._validate_symbol(
            symbol
        )

        with self._lock:
            self.positions.pop(
                normalized,
                None,
            )

    def pop_position(
        self,
        symbol: str,
    ) -> Position:
        """Remove and return a live position or raise ``KeyError``."""

        normalized = self._validate_symbol(
            symbol
        )

        with self._lock:
            try:
                return self.positions.pop(
                    normalized
                )
            except KeyError as error:
                raise KeyError(
                    f"Unknown position: {normalized}"
                ) from error

    def get_position(
        self,
        symbol: str,
    ) -> Position | None:
        """Return the shared live object, or ``None`` when missing."""

        normalized = self._validate_symbol(
            symbol
        )

        with self._lock:
            return self.positions.get(
                normalized
            )

    def get_position_copy(
        self,
        symbol: str,
    ) -> Position | None:
        """Return an isolated copy, or ``None`` when missing."""

        position = self.get_position(symbol)

        if position is None:
            return None

        return deepcopy(position)

    def require_position(
        self,
        symbol: str,
    ) -> Position:
        """Return the shared live object or raise ``KeyError``."""

        normalized = self._validate_symbol(
            symbol
        )

        with self._lock:
            try:
                return self.positions[
                    normalized
                ]
            except KeyError as error:
                raise KeyError(
                    f"Unknown position: {normalized}"
                ) from error

    def exists(
        self,
        symbol: str,
    ) -> bool:
        """Return whether a normalized symbol is tracked."""

        normalized = self._validate_symbol(
            symbol
        )

        with self._lock:
            return normalized in self.positions

    def all_positions(
        self,
    ) -> list[Position]:
        """Return a new list containing shared live objects."""

        with self._lock:
            return list(
                self.positions.values()
            )

    def snapshot(
        self,
    ) -> tuple[Position, ...]:
        """Return an isolated immutable container of position copies."""

        with self._lock:
            return tuple(
                deepcopy(
                    list(
                        self.positions.values()
                    )
                )
            )

    def total_unrealized_pnl(self) -> float:
        """Return finite aggregate unrealized PnL."""

        with self._lock:
            values = tuple(
                self._finite_number(
                    position.unrealized_pnl,
                    "unrealized_pnl",
                )
                for position
                in self.positions.values()
            )

        return self._finite_sum(
            values,
            "total unrealized_pnl",
        )

    def total_realized_pnl(self) -> float:
        """Return finite aggregate realized PnL."""

        with self._lock:
            values = tuple(
                self._finite_number(
                    position.realized_pnl,
                    "realized_pnl",
                )
                for position
                in self.positions.values()
            )

        return self._finite_sum(
            values,
            "total realized_pnl",
        )

    def equity(self) -> float:
        """Return balance plus unrealized PnL."""

        with self._lock:
            balance = self.balance

        result = (
            balance
            + self.total_unrealized_pnl()
        )

        if not isfinite(result):
            raise ValueError(
                "equity must be finite."
            )

        return float(result)

    def total_exposure(self) -> float:
        """Return gross absolute marked exposure."""

        with self._lock:
            values: list[float] = []

            for position in self.positions.values():
                price = self._position_mark_price(
                    position
                )
                size = self._position_size(
                    position
                )
                notional = abs(price * size)

                if not isfinite(notional):
                    raise ValueError(
                        "position exposure must be finite."
                    )

                values.append(float(notional))

        return self._finite_sum(
            values,
            "total exposure",
        )

    def net_exposure(self) -> float:
        """Return signed BUY-minus-SELL marked exposure."""

        with self._lock:
            values: list[float] = []

            for position in self.positions.values():
                price = self._position_mark_price(
                    position
                )
                size = self._position_size(
                    position
                )
                side = self._position_side(
                    position
                )
                notional = abs(price * size)
                signed = (
                    notional
                    if side == "BUY"
                    else -notional
                )

                if not isfinite(signed):
                    raise ValueError(
                        "position exposure must be finite."
                    )

                values.append(float(signed))

        return self._finite_sum(
            values,
            "net exposure",
        )

    def total_margin_used(self) -> float:
        """Return aggregate marked notional divided by leverage."""

        with self._lock:
            values: list[float] = []

            for position in self.positions.values():
                price = self._position_mark_price(
                    position
                )
                size = self._position_size(
                    position
                )
                leverage = self._finite_number(
                    position.leverage,
                    "position leverage",
                )

                if leverage <= 0.0:
                    raise ValueError(
                        "position leverage must be greater than zero."
                    )

                margin = (
                    abs(price * size)
                    / leverage
                )

                if not isfinite(margin):
                    raise ValueError(
                        "position margin must be finite."
                    )

                values.append(float(margin))

        return self._finite_sum(
            values,
            "total margin",
        )

    def available_balance(self) -> float:
        """Return balance minus marked margin usage."""

        result = (
            self.get_balance()
            - self.total_margin_used()
        )

        if not isfinite(result):
            raise ValueError(
                "available balance must be finite."
            )

        return float(result)

    def clear_positions(self) -> None:
        """Remove every tracked position."""

        with self._lock:
            self.positions.clear()

    def count(self) -> int:
        """Return the number of tracked positions."""

        return len(self)

    def __len__(self) -> int:
        with self._lock:
            return len(self.positions)

    def __bool__(self) -> bool:
        with self._lock:
            return bool(self.positions)

    def __iter__(self) -> Iterator[Position]:
        return iter(self.snapshot())


__all__ = (
    "PortfolioManager",
)