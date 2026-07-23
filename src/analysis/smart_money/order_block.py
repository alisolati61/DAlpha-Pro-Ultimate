"""Order-block candle classification and validation.

This module preserves the original single-candle ``detect`` contract.

Important:
    A single candle cannot independently confirm a structural order block.
    This engine classifies whether a candle is a valid bullish or bearish
    order-block candidate. Structural confirmation must be performed using
    subsequent displacement and break-of-structure data.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real


@dataclass(frozen=True, slots=True)
class OrderBlock:
    """Immutable result of order-block candidate detection.

    Attributes:
        bullish:
            True when the candle closes above its open.
        bearish:
            True when the candle closes below its open.
        high:
            Candle high.
        low:
            Candle low.
        valid:
            True only for a directional, structurally valid candle.

    A doji is represented by:

        bullish=False
        bearish=False
        valid=False
    """

    bullish: bool
    bearish: bool
    high: float
    low: float
    valid: bool

    def __post_init__(self) -> None:
        """Protect result invariants even during direct construction."""
        if not isinstance(self.bullish, bool):
            raise TypeError("bullish must be a bool")

        if not isinstance(self.bearish, bool):
            raise TypeError("bearish must be a bool")

        if not isinstance(self.valid, bool):
            raise TypeError("valid must be a bool")

        high = _validate_number("high", self.high)
        low = _validate_number("low", self.low)

        if high < low:
            raise ValueError("high must be greater than or equal to low")

        if self.bullish and self.bearish:
            raise ValueError(
                "an order-block candidate cannot be both bullish and bearish"
            )

        expected_valid = self.bullish ^ self.bearish

        if self.valid != expected_valid:
            raise ValueError(
                "valid must be true exactly when one direction is active"
            )

        object.__setattr__(self, "high", high)
        object.__setattr__(self, "low", low)

    @property
    def range_size(self) -> float:
        """Return the full high-to-low candle range."""
        return self.high - self.low

    @property
    def midpoint(self) -> float:
        """Return the midpoint of the candidate price zone."""
        return (self.high + self.low) / 2.0

    @property
    def direction(self) -> str | None:
        """Return ``bullish``, ``bearish`` or ``None`` for a doji."""
        if self.bullish:
            return "bullish"

        if self.bearish:
            return "bearish"

        return None


class OrderBlockEngine:
    """Classify a validated candle as an order-block candidate."""

    def detect(
        self,
        candle_open: float,
        candle_close: float,
        candle_high: float,
        candle_low: float,
    ) -> OrderBlock:
        """Detect the direction of a valid order-block candidate candle.

        Args:
            candle_open:
                Candle opening price.
            candle_close:
                Candle closing price.
            candle_high:
                Highest traded price.
            candle_low:
                Lowest traded price.

        Returns:
            An immutable :class:`OrderBlock` result.

        Raises:
            TypeError:
                When a supplied value is not a real numeric value.
            ValueError:
                When a value is NaN/infinite or OHLC relationships are
                impossible.
        """
        open_price = _validate_number("candle_open", candle_open)
        close_price = _validate_number("candle_close", candle_close)
        high_price = _validate_number("candle_high", candle_high)
        low_price = _validate_number("candle_low", candle_low)

        self._validate_ohlc(
            candle_open=open_price,
            candle_close=close_price,
            candle_high=high_price,
            candle_low=low_price,
        )

        bullish = close_price > open_price
        bearish = close_price < open_price

        return OrderBlock(
            bullish=bullish,
            bearish=bearish,
            high=high_price,
            low=low_price,
            valid=bullish ^ bearish,
        )

    @staticmethod
    def _validate_ohlc(
        *,
        candle_open: float,
        candle_close: float,
        candle_high: float,
        candle_low: float,
    ) -> None:
        """Validate logical OHLC relationships."""
        if candle_high < candle_low:
            raise ValueError(
                "candle_high must be greater than or equal to candle_low"
            )

        body_high = max(candle_open, candle_close)
        body_low = min(candle_open, candle_close)

        if candle_high < body_high:
            raise ValueError(
                "candle_high cannot be below candle_open or candle_close"
            )

        if candle_low > body_low:
            raise ValueError(
                "candle_low cannot be above candle_open or candle_close"
            )


def _validate_number(name: str, value: object) -> float:
    """Return a finite float or raise a descriptive validation error."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")

    numeric_value = float(value)

    if not isfinite(numeric_value):
        raise ValueError(f"{name} must be finite")

    return numeric_value


__all__ = ["OrderBlock", "OrderBlockEngine"]