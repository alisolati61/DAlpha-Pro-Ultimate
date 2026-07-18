from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class Position:
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


class PositionManager:

    def __init__(self) -> None:

        self.positions: dict[
            str,
            Position,
        ] = {}

    @staticmethod
    def _validate_symbol(
        symbol: str,
    ) -> str:

        if not isinstance(
            symbol,
            str,
        ):

            raise TypeError(
                "symbol must be a string."
            )

        symbol = symbol.strip()

        if not symbol:

            raise ValueError(
                "symbol cannot be empty."
            )

        return symbol

    @staticmethod
    def _validate_side(
        side: str,
    ) -> str:

        if not isinstance(
            side,
            str,
        ):

            raise TypeError(
                "side must be a string."
            )

        side = side.strip().upper()

        if side not in {
            "BUY",
            "SELL",
        }:

            raise ValueError(
                "side must be 'BUY' or 'SELL'."
            )

        return side

    @staticmethod
    def _validate_positive_finite(
        value: float,
        name: str,
    ) -> float:

        if isinstance(
            value,
            bool,
        ):

            raise TypeError(
                f"{name} must be a number."
            )

        if not isinstance(
            value,
            (int, float),
        ):

            raise TypeError(
                f"{name} must be a number."
            )

        value = float(value)

        if not math.isfinite(
            value
        ):

            raise ValueError(
                f"{name} must be finite."
            )

        if value <= 0:

            raise ValueError(
                f"{name} must be greater than zero."
            )

        return value

    @classmethod
    def _validate_position(
        cls,
        position: Position,
    ) -> Position:

        if not isinstance(
            position,
            Position,
        ):

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

        if position.current_price is not None:

            current_price = (
                cls._validate_positive_finite(
                    position.current_price,
                    "current_price",
                )
            )

        else:

            current_price = None

        stop_loss = position.stop_loss

        if stop_loss is not None:

            stop_loss = (
                cls._validate_positive_finite(
                    stop_loss,
                    "stop_loss",
                )
            )

        take_profit = position.take_profit

        if take_profit is not None:

            take_profit = (
                cls._validate_positive_finite(
                    take_profit,
                    "take_profit",
                )
            )

        if not isinstance(
            position.opened_at,
            datetime,
        ):

            raise TypeError(
                "opened_at must be a datetime."
            )

        if position.opened_at.tzinfo is None:

            raise ValueError(
                "opened_at must be timezone-aware."
            )

        return Position(
            symbol=symbol,
            side=side,
            size=size,
            entry_price=entry_price,
            current_price=current_price,
            unrealized_pnl=float(
                position.unrealized_pnl
            ),
            realized_pnl=float(
                position.realized_pnl
            ),
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit,
            opened_at=position.opened_at,
        )

    def open_position(
        self,
        position: Position,
    ) -> None:

        normalized = self._validate_position(
            position
        )

        if self.exists(
            normalized.symbol
        ):

            raise ValueError(
                "Position already exists."
            )

        self.positions[
            normalized.symbol
        ] = deepcopy(
            normalized
        )

    def close_position(
        self,
        symbol: str,
    ) -> Position:

        symbol = self._validate_symbol(
            symbol
        )

        if symbol not in self.positions:

            raise KeyError(
                f"Unknown position: {symbol}"
            )

        return deepcopy(
            self.positions.pop(symbol)
        )

    def get_position(
        self,
        symbol: str,
    ) -> Position | None:

        symbol = self._validate_symbol(
            symbol
        )

        position = self.positions.get(
            symbol
        )

        if position is None:

            return None

        return deepcopy(position)

    def list_positions(
        self,
    ) -> list[Position]:

        return [
            deepcopy(position)
            for position
            in self.positions.values()
        ]

    def update_price(
        self,
        symbol: str,
        price: float,
    ) -> None:

        symbol = self._validate_symbol(
            symbol
        )

        price = self._validate_positive_finite(
            price,
            "price",
        )

        position = self.positions.get(
            symbol
        )

        if position is None:

            raise KeyError(
                f"Unknown position: {symbol}"
            )

        position.current_price = price

        if position.side == "BUY":

            position.unrealized_pnl = (
                price - position.entry_price
            ) * position.size

        else:

            position.unrealized_pnl = (
                position.entry_price - price
            ) * position.size

    def exists(
        self,
        symbol: str,
    ) -> bool:

        symbol = self._validate_symbol(
            symbol
        )

        return symbol in self.positions

    def count(
        self,
    ) -> int:

        return len(self.positions)