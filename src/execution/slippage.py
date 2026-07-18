from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class SlippageResult:
    expected_price: float
    executed_price: float
    absolute_slippage: float
    slippage_percent: float
    adverse: bool


class SlippageCalculator:
    """
    Calculates execution slippage.

    For BUY orders:
        Higher execution price = adverse slippage.

    For SELL orders:
        Lower execution price = adverse slippage.
    """

    @staticmethod
    def _validate_price(
        price: float,
        name: str,
    ) -> float:

        if not isinstance(
            price,
            (int, float),
        ):

            raise TypeError(
                f"{name} must be a number."
            )

        price = float(price)

        if not math.isfinite(price):

            raise ValueError(
                f"{name} must be finite."
            )

        if price <= 0:

            raise ValueError(
                f"{name} must be greater than zero."
            )

        return price

    @staticmethod
    def _normalize_side(
        side: OrderSide | str,
    ) -> OrderSide:

        if isinstance(
            side,
            OrderSide,
        ):

            return side

        if not isinstance(
            side,
            str,
        ):

            raise TypeError(
                "side must be an OrderSide or string."
            )

        try:

            return OrderSide(
                side.strip().lower()
            )

        except ValueError as exc:

            raise ValueError(
                "side must be 'buy' or 'sell'."
            ) from exc

    @classmethod
    def calculate(
        cls,
        *,
        expected_price: float,
        executed_price: float,
        side: OrderSide | str,
    ) -> SlippageResult:

        expected = cls._validate_price(
            expected_price,
            "expected_price",
        )

        executed = cls._validate_price(
            executed_price,
            "executed_price",
        )

        normalized_side = cls._normalize_side(
            side
        )

        absolute_slippage = abs(
            executed - expected
        )

        slippage_percent = (
            absolute_slippage
            / expected
        ) * 100

        adverse = (
            (
                normalized_side
                is OrderSide.BUY
                and executed > expected
            )
            or
            (
                normalized_side
                is OrderSide.SELL
                and executed < expected
            )
        )

        return SlippageResult(
            expected_price=expected,
            executed_price=executed,
            absolute_slippage=float(
                absolute_slippage
            ),
            slippage_percent=float(
                slippage_percent
            ),
            adverse=adverse,
        )

    @classmethod
    def exceeds_limit(
        cls,
        *,
        expected_price: float,
        executed_price: float,
        side: OrderSide | str,
        max_slippage_percent: float,
    ) -> bool:

        if not isinstance(
            max_slippage_percent,
            (int, float),
        ):

            raise TypeError(
                "max_slippage_percent "
                "must be a number."
            )

        max_slippage_percent = float(
            max_slippage_percent
        )

        if not math.isfinite(
            max_slippage_percent
        ):

            raise ValueError(
                "max_slippage_percent "
                "must be finite."
            )

        if max_slippage_percent < 0:

            raise ValueError(
                "max_slippage_percent "
                "cannot be negative."
            )

        result = cls.calculate(
            expected_price=expected_price,
            executed_price=executed_price,
            side=side,
        )

        return (
            result.adverse
            and result.slippage_percent
            > max_slippage_percent
        )