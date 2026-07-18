from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import math


@dataclass(slots=True)
class PaperTrade:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    timestamp: datetime


class PaperTradingEngine:
    """
    Lightweight paper-trading execution engine.

    Executes simulated trades locally and stores
    immutable trade records in memory.
    """

    def __init__(self) -> None:
        self._trades: list[PaperTrade] = []

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

        side = side.strip().lower()

        if side not in {
            "buy",
            "sell",
        }:

            raise ValueError(
                "side must be 'buy' or 'sell'."
            )

        return side

    @staticmethod
    def _validate_positive_number(
        value: float,
        field_name: str,
    ) -> float:

        if isinstance(
            value,
            bool,
        ):

            raise TypeError(
                f"{field_name} must be a number."
            )

        if not isinstance(
            value,
            (int, float),
        ):

            raise TypeError(
                f"{field_name} must be a number."
            )

        value = float(value)

        if not math.isfinite(
            value,
        ):

            raise ValueError(
                f"{field_name} must be finite."
            )

        if value <= 0:

            raise ValueError(
                f"{field_name} must be greater than zero."
            )

        return value

    def execute(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ) -> PaperTrade:

        validated_symbol = self._validate_symbol(
            symbol,
        )

        validated_side = self._validate_side(
            side,
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

        trade = PaperTrade(
            symbol=validated_symbol,
            side=validated_side,
            quantity=validated_quantity,
            entry_price=validated_price,
            timestamp=datetime.now(UTC),
        )

        self._trades.append(
            trade,
        )

        return trade

    def history(self) -> list[PaperTrade]:

        return list(
            self._trades,
        )