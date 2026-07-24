"""Breaker-block formation and retest evaluation.

A breaker block is created when a valid order block is invalidated and market
structure subsequently breaks in the opposite direction.

Formation rules:
- Bearish order block invalidated + bullish BOS -> bullish breaker.
- Bullish order block invalidated + bearish BOS -> bearish breaker.
- Ambiguous or missing BOS never confirms a breaker.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real
from typing import Literal

from src.analysis.smart_money.bos import BOSResult
from src.analysis.smart_money.mitigation import MitigationResult
from src.analysis.smart_money.order_block import OrderBlock

InvalidationMode = Literal["close", "wick"]


@dataclass(frozen=True, slots=True)
class BreakerBlock:
    """Immutable breaker-block formation result."""

    bullish: bool
    bearish: bool
    zone_high: float
    zone_low: float
    confirmed: bool
    breakout_price: float | None

    def __post_init__(self) -> None:
        for name in ("bullish", "bearish", "confirmed"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")

        zone_high = _validate_number("zone_high", self.zone_high)
        zone_low = _validate_number("zone_low", self.zone_low)

        if zone_high <= zone_low:
            raise ValueError("zone_high must be greater than zone_low")

        active_directions = int(self.bullish) + int(self.bearish)

        if self.confirmed:
            if active_directions != 1:
                raise ValueError(
                    "a confirmed breaker must have exactly one active direction"
                )
            if self.breakout_price is None:
                raise ValueError(
                    "a confirmed breaker must have a breakout_price"
                )
        else:
            if active_directions != 0:
                raise ValueError(
                    "an unconfirmed breaker cannot have an active direction"
                )
            if self.breakout_price is not None:
                raise ValueError(
                    "an unconfirmed breaker cannot have a breakout_price"
                )

        breakout_price: float | None = None
        if self.breakout_price is not None:
            breakout_price = _validate_positive_number(
                "breakout_price",
                self.breakout_price,
            )
            if self.bullish and breakout_price <= zone_high:
                raise ValueError(
                    "bullish breakout_price must be above zone_high"
                )
            if self.bearish and breakout_price >= zone_low:
                raise ValueError(
                    "bearish breakout_price must be below zone_low"
                )

        object.__setattr__(self, "zone_high", zone_high)
        object.__setattr__(self, "zone_low", zone_low)
        object.__setattr__(self, "breakout_price", breakout_price)

    @property
    def direction(self) -> str | None:
        if self.bullish:
            return "bullish"
        if self.bearish:
            return "bearish"
        return None

    @property
    def zone_size(self) -> float:
        return self.zone_high - self.zone_low

    @property
    def midpoint(self) -> float:
        return (self.zone_high + self.zone_low) / 2.0


@dataclass(frozen=True, slots=True)
class BreakerRetestResult:
    """Immutable result of evaluating a candle against a confirmed breaker."""

    bullish: bool
    bearish: bool
    zone_high: float
    zone_low: float
    touched: bool
    rejected: bool
    invalidated: bool
    penetration_ratio: float

    def __post_init__(self) -> None:
        for name in (
            "bullish",
            "bearish",
            "touched",
            "rejected",
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
                "exactly one of bullish or bearish must be true"
            )

        if not 0.0 <= penetration_ratio <= 1.0:
            raise ValueError(
                "penetration_ratio must be between 0.0 and 1.0"
            )

        if not self.touched and penetration_ratio != 0.0:
            raise ValueError(
                "an untouched breaker must have zero penetration"
            )

        if self.rejected and not self.touched:
            raise ValueError(
                "a rejected breaker must also be touched"
            )

        if self.rejected and self.invalidated:
            raise ValueError(
                "a breaker cannot be both rejected and invalidated"
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
        return "bullish" if self.bullish else "bearish"


class BreakerBlockEngine:
    """Detect breaker formation and evaluate later retests."""

    def __init__(
        self,
        *,
        minimum_retest_penetration: float = 0.0,
        invalidation_mode: InvalidationMode = "close",
    ) -> None:
        penetration = _validate_number(
            "minimum_retest_penetration",
            minimum_retest_penetration,
        )

        if not 0.0 <= penetration <= 1.0:
            raise ValueError(
                "minimum_retest_penetration must be between 0.0 and 1.0"
            )

        if invalidation_mode not in ("close", "wick"):
            raise ValueError(
                "invalidation_mode must be either 'close' or 'wick'"
            )

        self._minimum_retest_penetration = penetration
        self._invalidation_mode = invalidation_mode
    @property
    def minimum_retest_penetration(self) -> float:
        return self._minimum_retest_penetration

    @property
    def invalidation_mode(self) -> InvalidationMode:
        return self._invalidation_mode

    def detect(
        self,
        order_block: OrderBlock,
        mitigation: MitigationResult,
        bos: BOSResult,
    ) -> BreakerBlock:
        """
        Detect whether an invalidated Order Block becomes a Breaker Block.
        """

        self._validate_dependencies(
            order_block,
            mitigation,
            bos,
        )

        bullish_breaker = (
            order_block.bearish
            and mitigation.invalidated
            and bos.bullish_bos
            and not bos.bearish_bos
            and bos.breakout_price is not None
            and bos.breakout_price > order_block.high
        )

        bearish_breaker = (
            order_block.bullish
            and mitigation.invalidated
            and bos.bearish_bos
            and not bos.bullish_bos
            and bos.breakout_price is not None
            and bos.breakout_price < order_block.low
        )

        confirmed = bullish_breaker or bearish_breaker

        return BreakerBlock(
            bullish=bullish_breaker,
            bearish=bearish_breaker,
            zone_high=order_block.high,
            zone_low=order_block.low,
            confirmed=confirmed,
            breakout_price=bos.breakout_price if confirmed else None,
        )

    def evaluate_retest(
        self,
        breaker: BreakerBlock,
        *,
        candle_high: float,
        candle_low: float,
        candle_close: float,
    ) -> BreakerRetestResult:
        """
        Evaluate a later retest of a confirmed breaker block.
        """

        if not isinstance(breaker, BreakerBlock):
            raise TypeError(
                "breaker must be a BreakerBlock instance"
            )

        if not breaker.confirmed:
            raise ValueError(
                "breaker must be confirmed"
            )

        high = _validate_positive_number(
            "candle_high",
            candle_high,
        )

        low = _validate_positive_number(
            "candle_low",
            candle_low,
        )

        close = _validate_positive_number(
            "candle_close",
            candle_close,
        )

        if high < low:
            raise ValueError(
                "candle_high must be greater than or equal to candle_low"
            )

        if close > high:
            raise ValueError(
                "candle_close cannot be above candle_high"
            )

        if close < low:
            raise ValueError(
                "candle_close cannot be below candle_low"
            )

        touched = (
            high >= breaker.zone_low
            and low <= breaker.zone_high
        )

        zone_size = breaker.zone_size

        if breaker.bullish:

            penetration = (
                _clamp(
                    (breaker.zone_high - low) / zone_size,
                    minimum=0.0,
                    maximum=1.0,
                )
                if touched
                else 0.0
            )

            if self._invalidation_mode == "wick":
                invalidated = (
                    low < breaker.zone_low
                )
            else:
                invalidated = (
                    close < breaker.zone_low
                )

            closed_in_rejection_direction = (
                close > breaker.zone_high
            )

        else:

            penetration = (
                _clamp(
                    (high - breaker.zone_low) / zone_size,
                    minimum=0.0,
                    maximum=1.0,
                )
                if touched
                else 0.0
            )

            if self._invalidation_mode == "wick":
                invalidated = (
                    high > breaker.zone_high
                )
            else:
                invalidated = (
                    close > breaker.zone_high
                )

            closed_in_rejection_direction = (
                close < breaker.zone_low
            )

        rejected = (
            touched
            and not invalidated
            and closed_in_rejection_direction
            and penetration
            >= self._minimum_retest_penetration
        )

        return BreakerRetestResult(
            bullish=breaker.bullish,
            bearish=breaker.bearish,
            zone_high=breaker.zone_high,
            zone_low=breaker.zone_low,
            touched=touched,
            rejected=rejected,
            invalidated=invalidated,
            penetration_ratio=penetration,
        )   
    @staticmethod
    def _validate_dependencies(
        order_block: OrderBlock,
        mitigation: MitigationResult,
        bos: BOSResult,
    ) -> None:

        if not isinstance(order_block, OrderBlock):
            raise TypeError(
                "order_block must be an OrderBlock instance"
            )

        if not isinstance(
            mitigation,
            MitigationResult,
        ):
            raise TypeError(
                "mitigation must be a MitigationResult instance"
            )

        if not isinstance(
            bos,
            BOSResult,
        ):
            raise TypeError(
                "bos must be a BOSResult instance"
            )

        if not order_block.valid:
            raise ValueError(
                "order_block must be valid"
            )

        if order_block.bullish == order_block.bearish:
            raise ValueError(
                "order_block must have exactly one active direction"
            )

        if mitigation.bullish != order_block.bullish:
            raise ValueError(
                "mitigation direction must match order_block direction"
            )

        if mitigation.bearish != order_block.bearish:
            raise ValueError(
                "mitigation direction must match order_block direction"
            )

        if mitigation.zone_high != order_block.high:
            raise ValueError(
                "mitigation zone_high must match order_block high"
            )

        if mitigation.zone_low != order_block.low:
            raise ValueError(
                "mitigation zone_low must match order_block low"
            )

        if bos.bullish_bos and bos.bearish_bos:
            if bos.breakout_price is not None:
                raise ValueError(
                    "ambiguous BOS must not have breakout_price"
                )
            return

        if bos.bullish_bos or bos.bearish_bos:

            if bos.breakout_price is None:
                raise ValueError(
                    "directional BOS must have breakout_price"
                )

            _validate_positive_number(
                "bos.breakout_price",
                bos.breakout_price,
            )

        else:

            if bos.breakout_price is not None:
                raise ValueError(
                    "BOS without direction cannot have breakout_price"
                )


def _validate_number(
    name: str,
    value: object,
) -> float:

    if isinstance(value, bool):
        raise TypeError(
            f"{name} must be a real number"
        )

    if not isinstance(value, Real):
        raise TypeError(
            f"{name} must be a real number"
        )

    value = float(value)

    if not isfinite(value):
        raise ValueError(
            f"{name} must be finite"
        )

    return value


def _validate_positive_number(
    name: str,
    value: object,
) -> float:

    value = _validate_number(
        name,
        value,
    )

    if value <= 0:
        raise ValueError(
            f"{name} must be greater than zero"
        )

    return value


def _clamp(
    value: float,
    *,
    minimum: float,
    maximum: float,
) -> float:

    if value < minimum:
        return minimum

    if value > maximum:
        return maximum

    return value


__all__ = [
    "BreakerBlock",
    "BreakerRetestResult",
    "BreakerBlockEngine",
    "InvalidationMode",
]