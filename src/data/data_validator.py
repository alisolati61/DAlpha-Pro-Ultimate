from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ValidationResult:
    valid: bool
    reason: str


class DataValidator:
    """
    Validates incoming market data before it enters DataManager.
    """

    REQUIRED_CANDLE_LENGTH = 6

    def validate(
        self,
        candles: list[list[Any]],
    ) -> ValidationResult:

        if not candles:
            return ValidationResult(
                False,
                "Empty candle list",
            )

        for candle in candles:

            if len(candle) < self.REQUIRED_CANDLE_LENGTH:

                return ValidationResult(
                    False,
                    "Invalid candle format",
                )

            o = float(candle[1])
            h = float(candle[2])
            l = float(candle[3])
            c = float(candle[4])

            if h < l:

                return ValidationResult(
                    False,
                    "High lower than Low",
                )

            if not (l <= o <= h):

                return ValidationResult(
                    False,
                    "Open outside range",
                )

            if not (l <= c <= h):

                return ValidationResult(
                    False,
                    "Close outside range",
                )

        return ValidationResult(
            True,
            "OK",
        )