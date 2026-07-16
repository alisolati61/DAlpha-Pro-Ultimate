from dataclasses import dataclass

from src.market.market_data import MarketData


@dataclass(slots=True)
class SupportResistance:
    support: float
    resistance: float


class SupportResistanceAnalyzer:
    """
    Basic Support / Resistance analyzer.

    MVP Version
    """

    @staticmethod
    def calculate(
        market: MarketData,
        distance_percent: float = 2.0,
    ) -> SupportResistance:

        support = market.last_price * (1 - distance_percent / 100)

        resistance = market.last_price * (1 + distance_percent / 100)

        return SupportResistance(
            support=support,
            resistance=resistance,
        )

    @staticmethod
    def near_support(
        market: MarketData,
        sr: SupportResistance,
        tolerance_percent: float = 0.5,
    ) -> bool:

        diff = abs(market.last_price - sr.support)

        return diff <= market.last_price * tolerance_percent / 100

    @staticmethod
    def near_resistance(
        market: MarketData,
        sr: SupportResistance,
        tolerance_percent: float = 0.5,
    ) -> bool:

        diff = abs(market.last_price - sr.resistance)

        return diff <= market.last_price * tolerance_percent / 100