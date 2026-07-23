"""Order-block mitigation detection.

This module evaluates whether a validated order-block zone has been revisited,
sufficiently penetrated, or invalidated by a subsequent candle.

Mitigation is intentionally separated from order-block detection:

- ``OrderBlockEngine`` classifies the candidate zone.
- ``MitigationEngine`` evaluates subsequent interaction with that zone.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real
from typing import Literal

from src.analysis.smart_money.order_block import OrderBlock

InvalidationMode = Literal["close", "wick"]


@dataclass(frozen=True, slots=True)
class MitigationResult:
    """Immutable result of an order-block mitigation evaluation.

    Attributes:
        bullish:
            True when the evaluated order block is bullish.
        bearish:
            True when the evaluated order block is bearish.
        zone_high:
            Upper boundary of the order-block zone.
        zone_low:
            Lower boundary of the order-block zone.
        touched:
            True when the candle range overlaps the order-block zone.
        mitigated:
            True when the zone has been penetrated by at least the configured
            minimum penetration and has not been invalidated.
        invalidated:
            True when price violates the invalidation boundary according to
            the selected invalidation mode.
        penetration_ratio:
            Direction-aware penetration into the zone, normalized to [0, 1].
            A value of 0 means no penetration and 1 means the entire zone has
            been traversed.
    """

    bullish: bool
    bearish: bool
    zone_high: float
    zone_low: float
    touched: bool
    mitigated: bool
    invalidated: bool
    penetration_ratio: float

    def __post_init__(self) -> None:
        """Protect result invariants during direct construction."""
        for name in (
            "bullish",
            "bearish",
            "touched",
            "mitigated",
            "invalidated",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")

        zone_high = _validate_number("zone_high", self.zone_high)
        zone_low = _validate_number("zone_low", self.zone_low)
        penetration_ratio = _validate_number(
            "penetration_ratio",
            self.penetration_ratio,
        )

        if zone_high <= zone_low:
            raise ValueError("zone_high must be greater than zone_low")

        if self.bullish == self.bearish:
            raise ValueError(
                "exactly one of bullish or bearish must be true",
            )

        if not 0.0 <= penetration_ratio <= 1.0:
            raise ValueError(
                "penetration_ratio must be between 0.0 and 1.0",
            )

        if self.mitigated and not self.touched:
            raise ValueError("a mitigated zone must also be touched")

        if self.mitigated and self.invalidated:
            raise ValueError(
                "a zone cannot be both mitigated and invalidated",
            )

        if not self.touched and penetration_ratio != 0.0:
            raise ValueError(
                "an untouched zone must have zero penetration",
            )

        object.__setattr__(self, "zone_high", zone_high)
        object.__setattr__(self, "zone_low", zone_low)
        object.__setattr__(
            self,
            "penetration_ratio",
            penetration_ratio,
        )

    @property
    def direction(self) -> str:
        """Return the order-block direction."""
        return "bullish" if self.bullish else "bearish"

    @property
    def zone_size(self) -> float:
        """Return the order-block zone height."""
        return self.zone_high - self.zone_low

    @property
    def fully_mitigated(self) -> bool:
        """Return whether the candle traversed the entire zone."""
        return self.mitigated and self.penetration_ratio == 1.0


class MitigationEngine:
    """Evaluate subsequent candle interaction with an order-block zone."""

    def __init__(
        self,
        *,
        minimum_penetration: float = 0.5,
        invalidation_mode: InvalidationMode = "close",
    ) -> None:
        """Initialize mitigation evaluation rules.

        Args:
            minimum_penetration:
                Minimum direction-aware zone penetration required for
                mitigation. Must be in the inclusive range [0, 1].
            invalidation_mode:
                ``"close"`` invalidates only when the candle closes beyond
                the protected boundary.

                ``"wick"`` invalidates as soon as the candle wick moves beyond
                the protected boundary.

        Raises:
            TypeError:
                If minimum_penetration is not a real number.
            ValueError:
                If configuration values are outside their supported ranges.
        """
        penetration = _validate_number(
            "minimum_penetration",
            minimum_penetration,
        )

        if not 0.0 <= penetration <= 1.0:
            raise ValueError(
                "minimum_penetration must be between 0.0 and 1.0",
            )

        if invalidation_mode not in ("close", "wick"):
            raise ValueError(
                "invalidation_mode must be either 'close' or 'wick'",
            )

        self._minimum_penetration = penetration
        self._invalidation_mode = invalidation_mode

    @property
    def minimum_penetration(self) -> float:
        """Return the configured mitigation threshold."""
        return self._minimum_penetration

    @property
    def invalidation_mode(self) -> InvalidationMode:
        """Return the configured invalidation mode."""
        return self._invalidation_mode

    def evaluate(
        self,
        order_block: OrderBlock,
        *,
        candle_high: float,
        candle_low: float,
        candle_close: float,
    ) -> MitigationResult:
        """Evaluate a subsequent candle against an order-block zone.

        Bullish order block:
            Price is expected to revisit the zone from above. Penetration is
            measured downward from ``zone_high`` toward ``zone_low``.
            Invalidation occurs below ``zone_low``.

        Bearish order block:
            Price is expected to revisit the zone from below. Penetration is
            measured upward from ``zone_low`` toward ``zone_high``.
            Invalidation occurs above ``zone_high``.

        Args:
            order_block:
                A valid directional ``OrderBlock`` instance.
            candle_high:
                Highest price of the subsequent candle.
            candle_low:
                Lowest price of the subsequent candle.
            candle_close:
                Closing price of the subsequent candle.

        Returns:
            Immutable mitigation evaluation result.

        Raises:
            TypeError:
                If order_block or candle values have invalid types.
            ValueError:
                If the order block is invalid, non-directional, or the candle
                values violate OHLC relationships.
        """
        if not isinstance(order_block, OrderBlock):
            raise TypeError("order_block must be an OrderBlock instance")

        if not order_block.valid:
            raise ValueError("order_block must be valid")

        if order_block.bullish == order_block.bearish:
            raise ValueError(
                "order_block must have exactly one active direction",
            )

        high = _validate_number("candle_high", candle_high)
        low = _validate_number("candle_low", candle_low)
        close = _validate_number("candle_close", candle_close)

        if high < low:
            raise ValueError(
                "candle_high must be greater than or equal to candle_low",
            )

        if close > high:
            raise ValueError("candle_close cannot be above candle_high")

        if close < low:
            raise ValueError("candle_close cannot be below candle_low")

        zone_high = _validate_number(
            "order_block.high",
            order_block.high,
        )
        zone_low = _validate_number(
            "order_block.low",
            order_block.low,
        )

        if zone_high <= zone_low:
            raise ValueError(
                "order-block zone must have a positive price range",
            )

        touched = high >= zone_low and low <= zone_high

        if order_block.bullish:
            penetration_ratio = self._bullish_penetration(
                candle_low=low,
                zone_high=zone_high,
                zone_low=zone_low,
                touched=touched,
            )
            invalidated = self._bullish_invalidated(
                candle_low=low,
                candle_close=close,
                zone_low=zone_low,
            )
        else:
            penetration_ratio = self._bearish_penetration(
                candle_high=high,
                zone_high=zone_high,
                zone_low=zone_low,
                touched=touched,
            )
            invalidated = self._bearish_invalidated(
                candle_high=high,
                candle_close=close,
                zone_high=zone_high,
            )

        mitigated = (
            touched
            and not invalidated
            and penetration_ratio >= self._minimum_penetration
        )

        return MitigationResult(
            bullish=order_block.bullish,
            bearish=order_block.bearish,
            zone_high=zone_high,
            zone_low=zone_low,
            touched=touched,
            mitigated=mitigated,
            invalidated=invalidated,
            penetration_ratio=penetration_ratio,
        )

    @staticmethod
    def _bullish_penetration(
        *,
        candle_low: float,
        zone_high: float,
        zone_low: float,
        touched: bool,
    ) -> float:
        if not touched:
            return 0.0

        zone_size = zone_high - zone_low
        raw_penetration = (zone_high - candle_low) / zone_size
        return _clamp(raw_penetration, minimum=0.0, maximum=1.0)

    @staticmethod
    def _bearish_penetration(
        *,
        candle_high: float,
        zone_high: float,
        zone_low: float,
        touched: bool,
    ) -> float:
        if not touched:
            return 0.0

        zone_size = zone_high - zone_low
        raw_penetration = (candle_high - zone_low) / zone_size
        return _clamp(raw_penetration, minimum=0.0, maximum=1.0)

    def _bullish_invalidated(
        self,
        *,
        candle_low: float,
        candle_close: float,
        zone_low: float,
    ) -> bool:
        if self._invalidation_mode == "wick":
            return candle_low < zone_low
        return candle_close < zone_low

    def _bearish_invalidated(
        self,
        *,
        candle_high: float,
        candle_close: float,
        zone_high: float,
    ) -> bool:
        if self._invalidation_mode == "wick":
            return candle_high > zone_high
        return candle_close > zone_high


def _validate_number(name: str, value: object) -> float:
    """Return a finite float or raise a descriptive validation error."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")

    numeric_value = float(value)

    if not isfinite(numeric_value):
        raise ValueError(f"{name} must be finite")

    return numeric_value


def _clamp(
    value: float,
    *,
    minimum: float,
    maximum: float,
) -> float:
    """Clamp a numeric value to the inclusive supplied range."""
    return max(minimum, min(value, maximum))


__all__ = [
    "InvalidationMode",
    "MitigationEngine",
    "MitigationResult",
]