from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LiquidityZone:
    """
    Result of liquidity-zone detection.

    buy_side:
        Liquidity resting above equal highs.

    sell_side:
        Liquidity resting below equal lows.

    price:
        Price of the detected liquidity zone.

    valid:
        True when exactly one valid liquidity zone is detected.
    """

    buy_side: bool
    sell_side: bool
    price: float | None
    valid: bool


class LiquidityEngine:
    """
    Detect basic buy-side and sell-side liquidity zones.

    Rules:
    - Equal highs create buy-side liquidity.
    - Equal lows create sell-side liquidity.
    - Both conditions cannot be represented by one LiquidityZone,
      because the result has only one price field.
    """

    @staticmethod
    def _validate_flag(
        value: bool,
        name: str,
    ) -> bool:
        if not isinstance(value, bool):
            raise TypeError(f"{name} must be a boolean")

        return value

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
        equal_high: bool,
        equal_low: bool,
        high_price: float,
        low_price: float,
    ) -> LiquidityZone:
        validated_equal_high = cls._validate_flag(
            equal_high,
            "equal_high",
        )
        validated_equal_low = cls._validate_flag(
            equal_low,
            "equal_low",
        )

        validated_high_price = cls._validate_price(
            high_price,
            "high_price",
        )
        validated_low_price = cls._validate_price(
            low_price,
            "low_price",
        )

        if validated_high_price <= validated_low_price:
            raise ValueError(
                "high_price must be greater than low_price"
            )

        if validated_equal_high and validated_equal_low:
            raise ValueError(
                "equal_high and equal_low cannot both be True"
            )

        if validated_equal_high:
            return LiquidityZone(
                buy_side=True,
                sell_side=False,
                price=validated_high_price,
                valid=True,
            )

        if validated_equal_low:
            return LiquidityZone(
                buy_side=False,
                sell_side=True,
                price=validated_low_price,
                valid=True,
            )

        return LiquidityZone(
            buy_side=False,
            sell_side=False,
            price=None,
            valid=False,
        )