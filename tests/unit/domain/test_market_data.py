from datetime import datetime

from src.domain.market_data import MarketData


def test_spread():

    data = MarketData(
        symbol="BTCUSDT",
        price=100000,
        bid=99990,
        ask=100010,
        volume=100,
        timestamp=datetime.now(),
    )

    assert data.spread == 20


def test_mid_price():

    data = MarketData(
        symbol="BTCUSDT",
        price=100000,
        bid=99990,
        ask=100010,
        volume=100,
        timestamp=datetime.now(),
    )

    assert data.mid_price == 100000