from src.intelligence.analyzers.trend_analyzer import TrendAnalyzer
from src.market.market_data import MarketData


def test_is_bullish():

    btc = MarketData(
        symbol="BTC/USDT",
        last_price=101,
        bid=100,
        ask=102,
        volume=100000,
    )

    assert TrendAnalyzer.is_bullish(btc)


def test_trend_score():

    btc = MarketData(
        symbol="BTC/USDT",
        last_price=101,
        bid=100,
        ask=102,
        volume=100000,
    )

    assert TrendAnalyzer.trend_score(btc) == 50.0