from __future__ import annotations

import math
from dataclasses import dataclass

from src.market.market_data import MarketData


@dataclass(frozen=True, slots=True)
class SupportResistance:
    support: float
    resistance: float


class SupportResistanceAnalyzer:
    """
    Percentage-based support and resistance analyzer.

    Support and resistance levels are calculated around the current
    market price using a configurable percentage distance.
    """

    @staticmethod
    def _validate_percentage(
        value: float,
        name: str,
    ) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a number")

        validated_value = float(value)

        if not math.isfinite(validated_value):
            raise ValueError(f"{name} must be finite")

        if validated_value < 0:
            raise ValueError(f"{name} must not be negative")

        return validated_value

    @staticmethod
    def _validate_market_price(market: MarketData) -> float:
        if not isinstance(market, MarketData):
            raise TypeError("market must be a MarketData instance")

        price = market.last_price

        if isinstance(price, bool) or not isinstance(price, (int, float)):
            raise TypeError("market.last_price must be a number")

        validated_price = float(price)

        if not math.isfinite(validated_price):
            raise ValueError("market.last_price must be finite")

        if validated_price <= 0:
            raise ValueError(
                "market.last_price must be greater than zero"
            )

        return validated_price

    @classmethod
    def calculate(
        cls,
        market: MarketData,
        distance_percent: float = 2.0,
    ) -> SupportResistance:
        price = cls._validate_market_price(market)

        distance = cls._validate_percentage(
            distance_percent,
            "distance_percent",
        )

        distance_ratio = distance / 100.0

        return SupportResistance(
            support=price * (1.0 - distance_ratio),
            resistance=price * (1.0 + distance_ratio),
        )

    @classmethod
    def near_support(
        cls,
        market: MarketData,
        levels: SupportResistance,
        tolerance_percent: float = 0.5,
    ) -> bool:
        price = cls._validate_market_price(market)

        if not isinstance(levels, SupportResistance):
            raise TypeError(
                "levels must be a SupportResistance instance"
            )

        tolerance = cls._validate_percentage(
            tolerance_percent,
            "tolerance_percent",
        )

        allowed_distance = price * tolerance / 100.0
        actual_distance = abs(price - levels.support)

        return actual_distance <= allowed_distance

    @classmethod
    def near_resistance(
        cls,
        market: MarketData,
        levels: SupportResistance,
        tolerance_percent: float = 0.5,
    ) -> bool:
        price = cls._validate_market_price(market)

        if not isinstance(levels, SupportResistance):
            raise TypeError(
                "levels must be a SupportResistance instance"
            )

        tolerance = cls._validate_percentage(
            tolerance_percent,
            "tolerance_percent",
        )

        allowed_distance = price * tolerance / 100.0
        actual_distance = abs(price - levels.resistance)

        return actual_distance <= allowed_distance