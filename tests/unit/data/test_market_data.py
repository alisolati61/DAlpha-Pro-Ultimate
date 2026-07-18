from datetime import UTC, datetime

from src.data.market_data import MarketData


def make_data():

    return MarketData(
        symbol="BTCUSDT",
        exchange="Binance",
        timeframe="1m",
        price=100,
        bid=99,
        ask=101,
        volume=500,
        timestamp=datetime.now(UTC),
    )


def test_create():

    data = make_data()

    assert isinstance(data, MarketData)


def test_spread():

    data = make_data()

    assert data.spread == 2.0


def test_symbol():

    data = make_data()

    assert data.symbol == "BTCUSDT"


def test_exchange():

    data = make_data()

    assert data.exchange == "Binance"


def test_types():

    data = make_data()

    assert isinstance(data.price, float)

    assert isinstance(data.bid, float)

    assert isinstance(data.ask, float)

    assert isinstance(data.volume, float)

    assert isinstance(data.timestamp, datetime)