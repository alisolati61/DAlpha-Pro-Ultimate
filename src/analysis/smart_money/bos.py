from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BOSResult:
    """
    Result of a Break of Structure detection.

    breakout_price is:
    - current_high for a bullish BOS
    - current_low for a bearish BOS
    - None when no BOS exists
    - None when both sides break simultaneously and direction is ambiguous
    """

    bullish_bos: bool
    bearish_bos: bool
    breakout_price: float | None


class BOSEngine:
    """
    Detect a basic Break of Structure from previous and current ranges.

    This engine preserves the project's existing public contract:

        detect(
            previous_high,
            previous_low,
            current_high,
            current_low,
        )

    Detection rules:
    - Bullish BOS: current high is strictly above previous high.
    - Bearish BOS: current low is strictly below previous low.
    - Equal levels are not considered a break.
    - If both boundaries break in the same observation, direction is
      ambiguous and breakout_price is None.
    """

    @staticmethod
    def _validate_price(
        value: float,
        name: str,
    ) -> float:
        if isinstance(value, bool) or not isinstance(
            value,
            (int, float),
        ):
            raise TypeError(f"{name} must be a number")

        validated_value = float(value)

        if not math.isfinite(validated_value):
            raise ValueError(f"{name} must be finite")

        if validated_value <= 0:
            raise ValueError(
                f"{name} must be greater than zero"
            )

        return validated_value

    @classmethod
    def detect(
        cls,
        previous_high: float,
        previous_low: float,
        current_high: float,
        current_low: float,
    ) -> BOSResult:
        validated_previous_high = cls._validate_price(
            previous_high,
            "previous_high",
        )
        validated_previous_low = cls._validate_price(
            previous_low,
            "previous_low",
        )
        validated_current_high = cls._validate_price(
            current_high,
            "current_high",
        )
        validated_current_low = cls._validate_price(
            current_low,
            "current_low",
        )

        if validated_previous_high <= validated_previous_low:
            raise ValueError(
                "previous_high must be greater than previous_low"
            )

        if validated_current_high < validated_current_low:
            raise ValueError(
                "current_high must be greater than or equal "
                "to current_low"
            )

        bullish = (
            validated_current_high > validated_previous_high
        )
        bearish = (
            validated_current_low < validated_previous_low
        )

        if bullish and bearish:
            breakout_price = None
        elif bullish:
            breakout_price = validated_current_high
        elif bearish:
            breakout_price = validated_current_low
        else:
            breakout_price = None

        return BOSResult(
            bullish_bos=bullish,
            bearish_bos=bearish,
            breakout_price=breakout_price,
        )