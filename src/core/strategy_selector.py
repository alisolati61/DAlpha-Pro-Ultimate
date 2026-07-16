from enum import Enum
from src.core.market_regime import MarketRegime


class Strategy(Enum):
    TREND_FOLLOWING = "TREND_FOLLOWING"
    BREAKOUT = "BREAKOUT"
    RANGE_TRADING = "RANGE_TRADING"
    SCALPING = "SCALPING"
    SWING = "SWING"


class StrategySelector:

    def select(self, regime: MarketRegime) -> Strategy:

        if regime == MarketRegime.TRENDING:
            return Strategy.TREND_FOLLOWING

        if regime == MarketRegime.RANGING:
            return Strategy.RANGE_TRADING

        if regime == MarketRegime.HIGH_VOLATILITY:
            return Strategy.BREAKOUT

        return Strategy.SCALPING