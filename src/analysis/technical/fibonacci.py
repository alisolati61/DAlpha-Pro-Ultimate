from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar, Literal

from src.analysis.technical.swing import SwingPoint


FibonacciDirection = Literal["BULLISH", "BEARISH"]


@dataclass(frozen=True, slots=True)
class FibonacciLevels:
    """
    Fibonacci retracement levels calculated between two swing points.

    For a bullish move:
        low -> high

    For a bearish move:
        high -> low
    """

    direction: FibonacciDirection
    start_price: float
    end_price: float
    level_0: float
    level_236: float
    level_382: float
    level_500: float
    level_618: float
    level_786: float
    level_100: float

    def as_dict(self) -> dict[float, float]:
        return {
            0.0: self.level_0,
            0.236: self.level_236,
            0.382: self.level_382,
            0.5: self.level_500,
            0.618: self.level_618,
            0.786: self.level_786,
            1.0: self.level_100,
        }


class FibonacciAnalyzer:
    """
    Calculate Fibonacci retracement levels from confirmed swing points.

    Expected swing order:

    Bullish:
        Swing LOW followed by Swing HIGH

    Bearish:
        Swing HIGH followed by Swing LOW
    """

    RATIOS: ClassVar[tuple[float, ...]] = (
        0.0,
        0.236,
        0.382,
        0.5,
        0.618,
        0.786,
        1.0,
    )

    @staticmethod
    def _validate_swing(
        swing: SwingPoint,
        name: str,
    ) -> None:
        if not isinstance(swing, SwingPoint):
            raise TypeError(f"{name} must be a SwingPoint instance")

        if isinstance(swing.index, bool) or not isinstance(
            swing.index,
            int,
        ):
            raise TypeError(f"{name}.index must be an integer")

        if swing.index < 0:
            raise ValueError(f"{name}.index must not be negative")

        if isinstance(swing.price, bool) or not isinstance(
            swing.price,
            (int, float),
        ):
            raise TypeError(f"{name}.price must be a number")

        if not math.isfinite(float(swing.price)):
            raise ValueError(f"{name}.price must be finite")

        if float(swing.price) <= 0:
            raise ValueError(
                f"{name}.price must be greater than zero"
            )

        if swing.kind not in ("HIGH", "LOW"):
            raise ValueError(
                f"{name}.kind must be either HIGH or LOW"
            )

    @classmethod
    def calculate(
        cls,
        start: SwingPoint,
        end: SwingPoint,
    ) -> FibonacciLevels:
        cls._validate_swing(start, "start")
        cls._validate_swing(end, "end")

        if start.index >= end.index:
            raise ValueError(
                "start swing must occur before end swing"
            )

        start_price = float(start.price)
        end_price = float(end.price)

        if start_price == end_price:
            raise ValueError(
                "start and end prices must be different"
            )

        if start.kind == "LOW" and end.kind == "HIGH":
            if start_price >= end_price:
                raise ValueError(
                    "bullish Fibonacci requires start price "
                    "below end price"
                )

            direction: FibonacciDirection = "BULLISH"
            difference = end_price - start_price

            level_0 = end_price
            level_236 = end_price - difference * 0.236
            level_382 = end_price - difference * 0.382
            level_500 = end_price - difference * 0.5
            level_618 = end_price - difference * 0.618
            level_786 = end_price - difference * 0.786
            level_100 = start_price

        elif start.kind == "HIGH" and end.kind == "LOW":
            if start_price <= end_price:
                raise ValueError(
                    "bearish Fibonacci requires start price "
                    "above end price"
                )

            direction = "BEARISH"
            difference = start_price - end_price

            level_0 = end_price
            level_236 = end_price + difference * 0.236
            level_382 = end_price + difference * 0.382
            level_500 = end_price + difference * 0.5
            level_618 = end_price + difference * 0.618
            level_786 = end_price + difference * 0.786
            level_100 = start_price

        else:
            raise ValueError(
                "swings must form LOW-to-HIGH or HIGH-to-LOW"
            )

        return FibonacciLevels(
            direction=direction,
            start_price=start_price,
            end_price=end_price,
            level_0=round(level_0, 8),
            level_236=round(level_236, 8),
            level_382=round(level_382, 8),
            level_500=round(level_500, 8),
            level_618=round(level_618, 8),
            level_786=round(level_786, 8),
            level_100=round(level_100, 8),
        )

    @staticmethod
    def nearest_level(
        price: float,
        levels: FibonacciLevels,
    ) -> tuple[float, float]:
        """
        Return the nearest Fibonacci ratio and its corresponding price.

        Example:
            (0.618, 106.18)
        """

        if isinstance(price, bool) or not isinstance(
            price,
            (int, float),
        ):
            raise TypeError("price must be a number")

        validated_price = float(price)

        if not math.isfinite(validated_price):
            raise ValueError("price must be finite")

        if validated_price <= 0:
            raise ValueError("price must be greater than zero")

        if not isinstance(levels, FibonacciLevels):
            raise TypeError(
                "levels must be a FibonacciLevels instance"
            )

        return min(
            levels.as_dict().items(),
            key=lambda item: abs(validated_price - item[1]),
        )