from enum import Enum


class MarketRegime(Enum):
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"


class MarketRegimeDetector:

    def detect(
        self,
        atr: float,
        adx: float,
    ) -> MarketRegime:

        if atr > 3:
            return MarketRegime.HIGH_VOLATILITY

        if adx >= 25:
            return MarketRegime.TRENDING

        if adx < 20:
            return MarketRegime.RANGING

        return MarketRegime.LOW_VOLATILITY