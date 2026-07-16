from src.intelligence.trend_discovery.engine import TrendDiscoveryEngine
from src.market.market_data import MarketData


def test_add_market_candidate():

    engine = TrendDiscoveryEngine()

    market = MarketData(
        symbol="BTC/USDT",
        last_price=100000,
        bid=99990,
        ask=100010,
        volume=1500000,
    )

    engine.add(market)

    assert engine.get_candidates() == [market]


def test_filter_by_volume():

    engine = TrendDiscoveryEngine()

    btc = MarketData(
        symbol="BTC/USDT",
        last_price=100000,
        bid=99990,
        ask=100010,
        volume=2000000,
    )

    meme = MarketData(
        symbol="MEME/USDT",
        last_price=1,
        bid=0.99,
        ask=1.01,
        volume=500,
    )

    engine.add(btc)
    engine.add(meme)

    result = engine.filter_by_volume(100000)

    assert result == [btc]