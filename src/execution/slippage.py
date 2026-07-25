"""Validated execution-slippage calculations.

Percentage values use percentage notation:

- ``1.0`` means 1%;
- ``0.25`` means 0.25%.

For BUY orders, an execution price above the expected price is adverse.
For SELL orders, an execution price below the expected price is adverse.

A slippage value equal to the configured maximum is allowed. A limit is
exceeded only when adverse slippage is strictly greater than the maximum.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from numbers import Real


class OrderSide(str, Enum):
    """Supported order sides for directional slippage."""

    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class SlippageResult:
    """Immutable result of one slippage calculation."""

    expected_price: float
    executed_price: float
    absolute_slippage: float
    slippage_percent: float
    adverse: bool

    @property
    def favorable(self) -> bool:
        """Return whether non-zero slippage improved execution."""

        return (
            not self.adverse
            and self.absolute_slippage > 0.0
        )

    @property
    def neutral(self) -> bool:
        """Return whether execution matched the expected price."""

        return self.absolute_slippage == 0.0

    @property
    def price_difference(self) -> float:
        """Return executed price minus expected price."""

        return float(
            self.executed_price
            - self.expected_price
        )

    @property
    def adverse_slippage_percent(self) -> float:
        """Return adverse slippage percentage, otherwise zero."""

        if self.adverse:
            return self.slippage_percent

        return 0.0

    @property
    def favorable_slippage_percent(self) -> float:
        """Return favorable slippage percentage, otherwise zero."""

        if self.favorable:
            return self.slippage_percent

        return 0.0


class SlippageCalculator:
    """Calculate directional execution slippage."""

    @staticmethod
    def _validate_price(
        price: object,
        name: str,
    ) -> float:
        if (
            isinstance(price, bool)
            or not isinstance(price, Real)
        ):
            raise TypeError(
                f"{name} must be a number."
            )

        normalized = float(price)

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
    def _normalize_side(
        side: OrderSide | str,
    ) -> OrderSide:
        if isinstance(side, OrderSide):
            return side

        if not isinstance(side, str):
            raise TypeError(
                "side must be an OrderSide or string."
            )

        normalized = side.strip().lower()

        try:
            return OrderSide(normalized)
        except ValueError as error:
            raise ValueError(
                "side must be 'buy' or 'sell'."
            ) from error

    @staticmethod
    def _validate_limit(
        max_slippage_percent: object,
    ) -> float:
        if (
            isinstance(max_slippage_percent, bool)
            or not isinstance(
                max_slippage_percent,
                Real,
            )
        ):
            raise TypeError(
                "max_slippage_percent "
                "must be a number."
            )

        normalized = float(
            max_slippage_percent
        )

        if not isfinite(normalized):
            raise ValueError(
                "max_slippage_percent "
                "must be finite."
            )

        if normalized < 0.0:
            raise ValueError(
                "max_slippage_percent "
                "cannot be negative."
            )

        return normalized

    @classmethod
    def calculate(
        cls,
        *,
        expected_price: float,
        executed_price: float,
        side: OrderSide | str,
    ) -> SlippageResult:
        """Calculate absolute and percentage execution slippage."""

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

        price_difference = executed - expected
        absolute_slippage = abs(
            price_difference
        )
        slippage_ratio = (
            absolute_slippage
            / expected
        )
        slippage_percent = (
            slippage_ratio
            * 100.0
        )

        if (
            not isfinite(slippage_ratio)
            or not isfinite(slippage_percent)
        ):
            raise ValueError(
                "slippage calculation must be finite."
            )

        adverse = (
            (
                normalized_side
                is OrderSide.BUY
                and price_difference > 0.0
            )
            or (
                normalized_side
                is OrderSide.SELL
                and price_difference < 0.0
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
            adverse=bool(adverse),
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
        """Return whether adverse slippage is strictly above the limit."""

        normalized_limit = cls._validate_limit(
            max_slippage_percent
        )
        result = cls.calculate(
            expected_price=expected_price,
            executed_price=executed_price,
            side=side,
        )

        return bool(
            result.adverse
            and result.slippage_percent
            > normalized_limit
        )

    @classmethod
    def within_limit(
        cls,
        *,
        expected_price: float,
        executed_price: float,
        side: OrderSide | str,
        max_slippage_percent: float,
    ) -> bool:
        """Return whether execution remains within the adverse limit."""

        return not cls.exceeds_limit(
            expected_price=expected_price,
            executed_price=executed_price,
            side=side,
            max_slippage_percent=(
                max_slippage_percent
            ),
        )


__all__ = (
    "OrderSide",
    "SlippageCalculator",
    "SlippageResult",
)