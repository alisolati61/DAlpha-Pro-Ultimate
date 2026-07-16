from src.intelligence.analyzers.market_analyzer import MarketAnalyzer
from src.market.market_data import MarketData


def test_spread():

    btc = MarketData(
        symbol="BTC/USDT",
        last_price=100,
        bid=99,
        ask=101,
        volume=100000,
    )

    assert MarketAnalyzer.spread(btc) == 2


def test_spread_percent():

    btc = MarketData(
        symbol="BTC/USDT",
        last_price=100,
        bid=99,
        ask=101,
        volume=100000,
    )

    assert MarketAnalyzer.spread_percent(btc) == 2.0


def test_liquidity():

    btc = MarketData(
        symbol="BTC/USDT",
        last_price=100,
        bid=99.95,
        ask=100.05,
        volume=100000,
    )

    assert MarketAnalyzer.is_liquid(btc)