from src.intelligence.analyzers.volume_analyzer import VolumeAnalyzer
from src.market.market_data import MarketData


def test_high_volume():

    btc = MarketData(
        symbol="BTC/USDT",
        last_price=100,
        bid=99,
        ask=101,
        volume=2_000_000,
    )

    assert VolumeAnalyzer.is_high_volume(btc, 1_000_000)


def test_volume_score():

    btc = MarketData(
        symbol="BTC/USDT",
        last_price=100,
        bid=99,
        ask=101,
        volume=500000,
    )

    assert VolumeAnalyzer.volume_score(btc, 1_000_000) == 50.0