"""Defensive validation for raw OHLCV candle batches."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ValidationResult:
    """Result returned by ``DataValidator`` without raising on bad input."""

    valid: bool
    reason: str


class DataValidator:
    """Validate raw exchange candles before they enter ``DataManager``.

    Candle layout is kept backward compatible with the existing pipeline:

    ``[timestamp, open, high, low, close, volume, ...]``

    Extra exchange-specific fields are allowed. Validation is deliberately
    non-throwing because this class sits on an external-data boundary.
    """

    REQUIRED_CANDLE_LENGTH = 6

    def validate(
        self,
        candles: Sequence[Sequence[Any]] | None,
    ) -> ValidationResult:
        """Return the first validation failure, or ``OK``."""

        if candles is None or isinstance(
            candles,
            (str, bytes, bytearray),
        ):
            return ValidationResult(
                False,
                "Invalid candle collection",
            )

        if not isinstance(candles, Sequence):
            return ValidationResult(
                False,
                "Invalid candle collection",
            )

        if not candles:
            return ValidationResult(
                False,
                "Empty candle list",
            )

        for candle in candles:
            result = self._validate_candle(candle)

            if not result.valid:
                return result

        return ValidationResult(
            True,
            "OK",
        )

    def _validate_candle(
        self,
        candle: Sequence[Any],
    ) -> ValidationResult:
        if isinstance(
            candle,
            (str, bytes, bytearray),
        ) or not isinstance(candle, Sequence):
            return ValidationResult(
                False,
                "Invalid candle format",
            )

        if len(candle) < self.REQUIRED_CANDLE_LENGTH:
            return ValidationResult(
                False,
                "Invalid candle format",
            )

        try:
            open_price = self._finite_number(candle[1])
            high_price = self._finite_number(candle[2])
            low_price = self._finite_number(candle[3])
            close_price = self._finite_number(candle[4])
            volume = self._finite_number(candle[5])
        except (TypeError, ValueError, OverflowError):
            return ValidationResult(
                False,
                "Invalid candle values",
            )

        if high_price < low_price:
            return ValidationResult(
                False,
                "High lower than Low",
            )

        if min(
            open_price,
            high_price,
            low_price,
            close_price,
        ) <= 0:
            return ValidationResult(
                False,
                "Non-positive price",
            )

        if not (low_price <= open_price <= high_price):
            return ValidationResult(
                False,
                "Open outside range",
            )

        if not (low_price <= close_price <= high_price):
            return ValidationResult(
                False,
                "Close outside range",
            )

        if volume < 0:
            return ValidationResult(
                False,
                "Negative volume",
            )

        return ValidationResult(
            True,
            "OK",
        )

    @staticmethod
    def _finite_number(value: Any) -> float:
        if isinstance(value, bool):
            raise TypeError("Boolean values are not numeric candle values.")

        number = float(value)

        if not math.isfinite(number):
            raise ValueError("Candle values must be finite.")

        return number


__all__ = (
    "DataValidator",
    "ValidationResult",
)