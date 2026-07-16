from src.core.strategy_selector import StrategySelector, Strategy
from src.core.market_regime import MarketRegime


def test_strategy_selector():
    selector = StrategySelector()

    trending = selector.select(MarketRegime.TRENDING)
    ranging = selector.select(MarketRegime.RANGING)
    high_volatility = selector.select(MarketRegime.HIGH_VOLATILITY)
    low_volatility = selector.select(MarketRegime.LOW_VOLATILITY)

    # خروجی باید Enum باشد
    assert isinstance(trending, Strategy)
    assert isinstance(ranging, Strategy)
    assert isinstance(high_volatility, Strategy)
    assert isinstance(low_volatility, Strategy)

    # مقادیر صحیح هر رژیم بازار
    assert trending == Strategy.TREND_FOLLOWING
    assert ranging == Strategy.RANGE_TRADING
    assert high_volatility == Strategy.BREAKOUT
    assert low_volatility == Strategy.SCALPING