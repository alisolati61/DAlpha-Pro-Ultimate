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
    Basic percentage-based support/resistance analyzer.

    This module preserves the existing MVP contract:
    levels are calculated around the current market price.
    """

    @staticmethod
    def _validate_percentage(
        value: float,
        name: str,
    ) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a number")

        value = float(value)

        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")

        if value < 0:
            raise ValueError(f"{name} must not be negative")

        return value

    @staticmethod
    def _validate_market_price(market: MarketData) -> float:
        price = market.last_price

        if isinstance(price, bool) or not isinstance(price, (int, float)):
            raise TypeError("market.last_price must be a number")

        price = float(price)

        if not math.isfinite(price):
            raise ValueError("market.last_price must be finite")

        if price <= 0:
            raise ValueError("market.last_price must be greater than zero")

        return price

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

        ratio = distance / 100.0

        return SupportResistance(
            support=price * (1.0 - ratio),
            resistance=price * (1.0 + ratio),
        )

    @classmethod
    def near_support(
        cls,
        market: MarketData,
        sr: SupportResistance,
        tolerance_percent: float = 0.5,
    ) -> bool:
        price = cls._validate_market_price(market)
        tolerance = cls._validate_percentage(
            tolerance_percent,
            "tolerance_percent",
        )

        difference = abs(price - sr.support)
        return difference <= price * tolerance / 100.0

    @classmethod
    def near_resistance(
        cls,
        market: MarketData,
        sr: SupportResistance,
        tolerance_percent: float = 0.5,
    ) -> bool:
        price = cls._validate_market_price(market)
        tolerance = cls._validate_percentage(
            tolerance_percent,
            "tolerance_percent",
        )

        difference = abs(price - sr.resistance)
        return difference <= price * tolerance / 100.0