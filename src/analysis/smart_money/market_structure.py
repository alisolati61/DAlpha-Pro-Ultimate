"""Market-structure classification from aligned high and low series.

The engine classifies every observation after the first as a higher high,
higher low, lower high, or lower low relative to the immediately preceding
observation. Equal levels are intentionally left unclassified.

The current trend preserves the module's original contract and is determined
from the final two aligned ranges:
- higher high + higher low -> bullish;
- lower high + lower low -> bearish;
- every mixed or equal combination -> sideways.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from numbers import Real


class Trend(str, Enum):
    """Supported market-structure directions."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    SIDEWAYS = "SIDEWAYS"


@dataclass(frozen=True, slots=True)
class SwingPoint:
    """A validated structural point in the analyzed series."""

    index: int
    price: float

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int):
            raise TypeError("index must be an integer")

        if self.index < 0:
            raise ValueError(
                "index must be greater than or equal to zero"
            )

        price = _validate_price("price", self.price)
        object.__setattr__(self, "price", price)


@dataclass(frozen=True, slots=True)
class MarketStructure:
    """Immutable market-structure analysis result."""

    trend: Trend
    higher_highs: tuple[SwingPoint, ...]
    higher_lows: tuple[SwingPoint, ...]
    lower_highs: tuple[SwingPoint, ...]
    lower_lows: tuple[SwingPoint, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.trend, Trend):
            raise TypeError("trend must be a Trend instance")

        higher_highs = _normalize_swing_points(
            "higher_highs",
            self.higher_highs,
        )
        higher_lows = _normalize_swing_points(
            "higher_lows",
            self.higher_lows,
        )
        lower_highs = _normalize_swing_points(
            "lower_highs",
            self.lower_highs,
        )
        lower_lows = _normalize_swing_points(
            "lower_lows",
            self.lower_lows,
        )

        _validate_unique_indexes(
            "higher_highs",
            higher_highs,
        )
        _validate_unique_indexes(
            "higher_lows",
            higher_lows,
        )
        _validate_unique_indexes(
            "lower_highs",
            lower_highs,
        )
        _validate_unique_indexes(
            "lower_lows",
            lower_lows,
        )

        _validate_disjoint_indexes(
            "higher_highs",
            higher_highs,
            "lower_highs",
            lower_highs,
        )
        _validate_disjoint_indexes(
            "higher_lows",
            higher_lows,
            "lower_lows",
            lower_lows,
        )

        object.__setattr__(
            self,
            "higher_highs",
            higher_highs,
        )
        object.__setattr__(
            self,
            "higher_lows",
            higher_lows,
        )
        object.__setattr__(
            self,
            "lower_highs",
            lower_highs,
        )
        object.__setattr__(
            self,
            "lower_lows",
            lower_lows,
        )

    @property
    def bullish(self) -> bool:
        return self.trend is Trend.BULLISH

    @property
    def bearish(self) -> bool:
        return self.trend is Trend.BEARISH

    @property
    def sideways(self) -> bool:
        return self.trend is Trend.SIDEWAYS

    @property
    def structural_point_count(self) -> int:
        """Return the total number of classified high/low movements."""

        return (
            len(self.higher_highs)
            + len(self.higher_lows)
            + len(self.lower_highs)
            + len(self.lower_lows)
        )

    @property
    def latest_higher_high(self) -> SwingPoint | None:
        if not self.higher_highs:
            return None

        return self.higher_highs[-1]

    @property
    def latest_higher_low(self) -> SwingPoint | None:
        if not self.higher_lows:
            return None

        return self.higher_lows[-1]

    @property
    def latest_lower_high(self) -> SwingPoint | None:
        if not self.lower_highs:
            return None

        return self.lower_highs[-1]

    @property
    def latest_lower_low(self) -> SwingPoint | None:
        if not self.lower_lows:
            return None

        return self.lower_lows[-1]


class MarketStructureEngine:
    """Analyze aligned high and low observations."""

    def analyze(
        self,
        highs: Iterable[Real],
        lows: Iterable[Real],
    ) -> MarketStructure:
        """Return classified structure for the supplied aligned ranges."""

        validated_highs = _normalize_prices(
            "highs",
            highs,
        )
        validated_lows = _normalize_prices(
            "lows",
            lows,
        )

        if len(validated_highs) != len(validated_lows):
            raise ValueError(
                "highs and lows must have the same length"
            )

        for index, (high, low) in enumerate(
            zip(
                validated_highs,
                validated_lows,
                strict=True,
            )
        ):
            if high < low:
                raise ValueError(
                    f"highs[{index}] must be greater than or equal "
                    f"to lows[{index}]"
                )

        higher_highs: list[SwingPoint] = []
        higher_lows: list[SwingPoint] = []
        lower_highs: list[SwingPoint] = []
        lower_lows: list[SwingPoint] = []

        for index in range(1, len(validated_highs)):
            current_high = validated_highs[index]
            previous_high = validated_highs[index - 1]

            current_low = validated_lows[index]
            previous_low = validated_lows[index - 1]

            if current_high > previous_high:
                higher_highs.append(
                    SwingPoint(
                        index=index,
                        price=current_high,
                    )
                )
            elif current_high < previous_high:
                lower_highs.append(
                    SwingPoint(
                        index=index,
                        price=current_high,
                    )
                )

            if current_low > previous_low:
                higher_lows.append(
                    SwingPoint(
                        index=index,
                        price=current_low,
                    )
                )
            elif current_low < previous_low:
                lower_lows.append(
                    SwingPoint(
                        index=index,
                        price=current_low,
                    )
                )

        trend = self._determine_trend(
            validated_highs,
            validated_lows,
        )

        return MarketStructure(
            trend=trend,
            higher_highs=tuple(higher_highs),
            higher_lows=tuple(higher_lows),
            lower_highs=tuple(lower_highs),
            lower_lows=tuple(lower_lows),
        )

    @staticmethod
    def _determine_trend(
        highs: tuple[float, ...],
        lows: tuple[float, ...],
    ) -> Trend:
        if len(highs) < 2:
            return Trend.SIDEWAYS

        high_change = highs[-1] - highs[-2]
        low_change = lows[-1] - lows[-2]

        if high_change > 0.0 and low_change > 0.0:
            return Trend.BULLISH

        if high_change < 0.0 and low_change < 0.0:
            return Trend.BEARISH

        return Trend.SIDEWAYS


def _normalize_prices(
    name: str,
    values: object,
) -> tuple[float, ...]:
    if isinstance(
        values,
        (str, bytes, bytearray),
    ):
        raise TypeError(
            f"{name} must be an iterable of real numbers"
        )

    try:
        iterator = iter(values)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError(
            f"{name} must be an iterable of real numbers"
        ) from exc

    return tuple(
        _validate_price(
            f"{name}[{index}]",
            value,
        )
        for index, value in enumerate(iterator)
    )


def _validate_price(
    name: str,
    value: object,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(
            f"{name} must be a real number"
        )

    numeric_value = float(value)

    if not isfinite(numeric_value):
        raise ValueError(
            f"{name} must be finite"
        )

    if numeric_value <= 0.0:
        raise ValueError(
            f"{name} must be greater than zero"
        )

    return numeric_value


def _normalize_swing_points(
    name: str,
    values: object,
) -> tuple[SwingPoint, ...]:
    if isinstance(
        values,
        (str, bytes, bytearray),
    ):
        raise TypeError(
            f"{name} must be an iterable of SwingPoint instances"
        )

    try:
        points = tuple(values)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError(
            f"{name} must be an iterable of SwingPoint instances"
        ) from exc

    for point in points:
        if not isinstance(point, SwingPoint):
            raise TypeError(
                f"{name} must contain only SwingPoint instances"
            )

    return points


def _validate_unique_indexes(
    name: str,
    points: tuple[SwingPoint, ...],
) -> None:
    indexes = [
        point.index
        for point in points
    ]

    if len(indexes) != len(set(indexes)):
        raise ValueError(
            f"{name} cannot contain duplicate indexes"
        )

    if indexes != sorted(indexes):
        raise ValueError(
            f"{name} must be ordered by index"
        )


def _validate_disjoint_indexes(
    first_name: str,
    first_points: tuple[SwingPoint, ...],
    second_name: str,
    second_points: tuple[SwingPoint, ...],
) -> None:
    shared_indexes = {
        point.index
        for point in first_points
    }.intersection(
        point.index
        for point in second_points
    )

    if shared_indexes:
        raise ValueError(
            f"{first_name} and {second_name} cannot share indexes"
        )


__all__ = [
    "MarketStructure",
    "MarketStructureEngine",
    "SwingPoint",
    "Trend",
]