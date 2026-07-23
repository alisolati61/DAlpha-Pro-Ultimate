from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal


TrendDirection = Literal["BULLISH", "BEARISH"]


@dataclass(frozen=True, slots=True)
class CHOCHResult:
    """
    Result of a Change of Character detection.

    bullish_choch:
        A previous bearish structure is broken upward.

    bearish_choch:
        A previous bullish structure is broken downward.

    reversal_price:
        The price that invalidated the previous structure.
    """

    bullish_choch: bool
    bearish_choch: bool
    reversal_price: float | None


class CHOCHEngine:
    """
    Detect a basic Change of Character.

    Detection rules:

    - Bullish CHOCH:
      Previous trend is BEARISH and current high breaks above
      the previous structural high.

    - Bearish CHOCH:
      Previous trend is BULLISH and current low breaks below
      the previous structural low.

    Equal highs or lows do not count as structural breaks.
    """

    VALID_TRENDS = frozenset({"BULLISH", "BEARISH"})

    @staticmethod
    def _validate_trend(previous_trend: str) -> TrendDirection:
        if not isinstance(previous_trend, str):
            raise TypeError("previous_trend must be a string")

        normalized_trend = previous_trend.strip().upper()

        if normalized_trend not in CHOCHEngine.VALID_TRENDS:
            raise ValueError(
                "previous_trend must be either BULLISH or BEARISH"
            )

        return normalized_trend  # type: ignore[return-value]

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
        previous_trend: str,
        current_high: float,
        previous_high: float,
        current_low: float,
        previous_low: float,
    ) -> CHOCHResult:
        validated_trend = cls._validate_trend(previous_trend)

        validated_current_high = cls._validate_price(
            current_high,
            "current_high",
        )
        validated_previous_high = cls._validate_price(
            previous_high,
            "previous_high",
        )
        validated_current_low = cls._validate_price(
            current_low,
            "current_low",
        )
        validated_previous_low = cls._validate_price(
            previous_low,
            "previous_low",
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

        bullish_choch = (
            validated_trend == "BEARISH"
            and validated_current_high > validated_previous_high
        )

        bearish_choch = (
            validated_trend == "BULLISH"
            and validated_current_low < validated_previous_low
        )

        reversal_price: float | None = None

        if bullish_choch:
            reversal_price = validated_current_high
        elif bearish_choch:
            reversal_price = validated_current_low

        return CHOCHResult(
            bullish_choch=bullish_choch,
            bearish_choch=bearish_choch,
            reversal_price=reversal_price,
        )