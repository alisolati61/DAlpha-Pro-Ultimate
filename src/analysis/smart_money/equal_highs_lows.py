"""Equal-high and equal-low detection.

The engine compares two validated market ranges and detects whether their
highs and/or lows are equal within configured absolute and relative
tolerances.

Representative levels use conservative outer boundaries:
- equal-high price: the higher of the two highs;
- equal-low price: the lower of the two lows.

This prevents downstream liquidity logic from treating a near-equal cluster
as swept before price crosses the full cluster.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real


@dataclass(frozen=True, slots=True)
class EqualHighLowResult:
    """Immutable equal-high/equal-low detection result."""

    equal_high: bool
    equal_low: bool
    high_price: float | None
    low_price: float | None

    def __post_init__(self) -> None:
        if not isinstance(self.equal_high, bool):
            raise TypeError("equal_high must be a bool")

        if not isinstance(self.equal_low, bool):
            raise TypeError("equal_low must be a bool")

        high_price = self._validate_optional_level(
            enabled=self.equal_high,
            value=self.high_price,
            flag_name="equal_high",
            value_name="high_price",
        )
        low_price = self._validate_optional_level(
            enabled=self.equal_low,
            value=self.low_price,
            flag_name="equal_low",
            value_name="low_price",
        )

        if (
            high_price is not None
            and low_price is not None
            and high_price < low_price
        ):
            raise ValueError(
                "high_price must be greater than or equal to low_price"
            )

        object.__setattr__(self, "high_price", high_price)
        object.__setattr__(self, "low_price", low_price)

    @staticmethod
    def _validate_optional_level(
        *,
        enabled: bool,
        value: object,
        flag_name: str,
        value_name: str,
    ) -> float | None:
        if enabled:
            if value is None:
                raise ValueError(
                    f"{value_name} is required when {flag_name} is true"
                )

            return _validate_positive_number(value_name, value)

        if value is not None:
            raise ValueError(
                f"{value_name} must be None when {flag_name} is false"
            )

        return None

    @property
    def valid(self) -> bool:
        """Return whether at least one equal level was detected."""
        return self.equal_high or self.equal_low

    @property
    def both(self) -> bool:
        """Return whether both equal highs and equal lows were detected."""
        return self.equal_high and self.equal_low

    @property
    def liquidity_level_count(self) -> int:
        """Return the number of detected liquidity levels."""
        return int(self.equal_high) + int(self.equal_low)


class EqualHighLowEngine:
    """Detect equal highs and equal lows between two market ranges.

    Two levels are equal when their difference is less than or equal to the
    larger of the configured absolute and relative tolerances.
    """

    def __init__(
        self,
        *,
        absolute_tolerance: float = 0.0,
        relative_tolerance: float = 0.0,
    ) -> None:
        absolute = _validate_non_negative_number(
            "absolute_tolerance",
            absolute_tolerance,
        )
        relative = _validate_non_negative_number(
            "relative_tolerance",
            relative_tolerance,
        )

        if relative > 1.0:
            raise ValueError(
                "relative_tolerance must be between 0.0 and 1.0"
            )

        self._absolute_tolerance = absolute
        self._relative_tolerance = relative

    @property
    def absolute_tolerance(self) -> float:
        """Return the configured absolute price tolerance."""
        return self._absolute_tolerance

    @property
    def relative_tolerance(self) -> float:
        """Return the configured relative price tolerance."""
        return self._relative_tolerance

    def detect(
        self,
        previous_high: float,
        previous_low: float,
        current_high: float,
        current_low: float,
    ) -> EqualHighLowResult:
        """Compare two market ranges and return detected equal levels."""

        validated_previous_high = _validate_positive_number(
            "previous_high",
            previous_high,
        )
        validated_previous_low = _validate_positive_number(
            "previous_low",
            previous_low,
        )
        validated_current_high = _validate_positive_number(
            "current_high",
            current_high,
        )
        validated_current_low = _validate_positive_number(
            "current_low",
            current_low,
        )

        self._validate_range(
            high=validated_previous_high,
            low=validated_previous_low,
            range_name="previous",
        )
        self._validate_range(
            high=validated_current_high,
            low=validated_current_low,
            range_name="current",
        )

        equal_high = self._levels_are_equal(
            validated_previous_high,
            validated_current_high,
        )
        equal_low = self._levels_are_equal(
            validated_previous_low,
            validated_current_low,
        )

        return EqualHighLowResult(
            equal_high=equal_high,
            equal_low=equal_low,
            high_price=(
                max(
                    validated_previous_high,
                    validated_current_high,
                )
                if equal_high
                else None
            ),
            low_price=(
                min(
                    validated_previous_low,
                    validated_current_low,
                )
                if equal_low
                else None
            ),
        )

    def _levels_are_equal(
        self,
        first: float,
        second: float,
    ) -> bool:
        relative_limit = (
            max(first, second)
            * self._relative_tolerance
        )

        allowed_difference = max(
            self._absolute_tolerance,
            relative_limit,
        )

        return abs(first - second) <= allowed_difference

    @staticmethod
    def _validate_range(
        *,
        high: float,
        low: float,
        range_name: str,
    ) -> None:
        if high < low:
            raise ValueError(
                f"{range_name}_high must be greater than or equal "
                f"to {range_name}_low"
            )


def _validate_number(
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

    return numeric_value


def _validate_positive_number(
    name: str,
    value: object,
) -> float:
    numeric_value = _validate_number(
        name,
        value,
    )

    if numeric_value <= 0.0:
        raise ValueError(
            f"{name} must be greater than zero"
        )

    return numeric_value


def _validate_non_negative_number(
    name: str,
    value: object,
) -> float:
    numeric_value = _validate_number(
        name,
        value,
    )

    if numeric_value < 0.0:
        raise ValueError(
            f"{name} must be greater than or equal to zero"
        )

    return numeric_value


__all__ = [
    "EqualHighLowEngine",
    "EqualHighLowResult",
]