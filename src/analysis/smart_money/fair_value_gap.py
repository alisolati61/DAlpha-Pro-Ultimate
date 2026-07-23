from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FairValueGap:
    """
    Result of a three-candle Fair Value Gap detection.

    For a bullish FVG:
        bottom = candle1_high
        top = candle3_low

    For a bearish FVG:
        bottom = candle3_high
        top = candle1_low

    When no FVG exists:
        top = None
        bottom = None
        valid = False
    """

    bullish: bool
    bearish: bool
    top: float | None
    bottom: float | None
    valid: bool

    def __post_init__(self) -> None:
        if self.bullish and self.bearish:
            raise ValueError(
                "FairValueGap cannot be both bullish and bearish"
            )

        if self.valid:
            if not self.bullish and not self.bearish:
                raise ValueError(
                    "A valid FairValueGap must have a direction"
                )

            if self.top is None or self.bottom is None:
                raise ValueError(
                    "A valid FairValueGap must have top and bottom"
                )

            if self.top <= self.bottom:
                raise ValueError(
                    "FairValueGap top must be greater than bottom"
                )
        else:
            if self.bullish or self.bearish:
                raise ValueError(
                    "An invalid FairValueGap cannot have a direction"
                )

            if self.top is not None or self.bottom is not None:
                raise ValueError(
                    "An invalid FairValueGap cannot have boundaries"
                )

    @property
    def size(self) -> float:
        """
        Return the absolute size of the gap.

        Returns zero when no valid gap exists.
        """
        if not self.valid:
            return 0.0

        if self.top is None or self.bottom is None:
            return 0.0

        return self.top - self.bottom

    @property
    def midpoint(self) -> float | None:
        """
        Return the midpoint, also known as consequent encroachment.

        Returns None when no valid gap exists.
        """
        if not self.valid:
            return None

        if self.top is None or self.bottom is None:
            return None

        return (self.top + self.bottom) / 2.0


class FairValueGapEngine:
    """
    Detect a classic three-candle Fair Value Gap.

    Detection rules:

    Bullish FVG:
        candle3_low > candle1_high

    Bearish FVG:
        candle3_high < candle1_low

    Candle two is part of the three-candle formation, although its prices
    do not directly define the gap boundaries.

    Equal boundaries do not form a Fair Value Gap.
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

    @staticmethod
    def _validate_candle(
        high: float,
        low: float,
        candle_name: str,
    ) -> None:
        if high < low:
            raise ValueError(
                f"{candle_name}_high must be greater than or equal "
                f"to {candle_name}_low"
            )

    @classmethod
    def detect(
        cls,
        candle1_high: float,
        candle1_low: float,
        candle2_high: float,
        candle2_low: float,
        candle3_high: float,
        candle3_low: float,
    ) -> FairValueGap:
        validated_candle1_high = cls._validate_price(
            candle1_high,
            "candle1_high",
        )
        validated_candle1_low = cls._validate_price(
            candle1_low,
            "candle1_low",
        )
        validated_candle2_high = cls._validate_price(
            candle2_high,
            "candle2_high",
        )
        validated_candle2_low = cls._validate_price(
            candle2_low,
            "candle2_low",
        )
        validated_candle3_high = cls._validate_price(
            candle3_high,
            "candle3_high",
        )
        validated_candle3_low = cls._validate_price(
            candle3_low,
            "candle3_low",
        )

        cls._validate_candle(
            validated_candle1_high,
            validated_candle1_low,
            "candle1",
        )
        cls._validate_candle(
            validated_candle2_high,
            validated_candle2_low,
            "candle2",
        )
        cls._validate_candle(
            validated_candle3_high,
            validated_candle3_low,
            "candle3",
        )

        bullish = (
            validated_candle3_low
            > validated_candle1_high
        )
        bearish = (
            validated_candle3_high
            < validated_candle1_low
        )

        if bullish:
            return FairValueGap(
                bullish=True,
                bearish=False,
                top=validated_candle3_low,
                bottom=validated_candle1_high,
                valid=True,
            )

        if bearish:
            return FairValueGap(
                bullish=False,
                bearish=True,
                top=validated_candle1_low,
                bottom=validated_candle3_high,
                valid=True,
            )

        return FairValueGap(
            bullish=False,
            bearish=False,
            top=None,
            bottom=None,
            valid=False,
        )