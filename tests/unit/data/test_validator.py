from datetime import datetime

from src.data.validator import MarketDataValidator
from src.domain.market_data import MarketData


def create_data():

    return MarketData(
        symbol="BTCUSDT",
        price=100000,
        bid=99990,
        ask=100010,
        volume=100,
        timestamp=datetime.now(),
    )


def test_valid():

    validator = MarketDataValidator()

    assert validator.validate(create_data())


def test_negative_price():

    validator = MarketDataValidator()

    data = create_data()

    data.price = -1

    assert not validator.validate(data)


def test_negative_bid():

    validator = MarketDataValidator()

    data = create_data()

    data.bid = -5

    assert not validator.validate(data)


def test_negative_ask():

    validator = MarketDataValidator()

    data = create_data()

    data.ask = -10

    assert not validator.validate(data)


def test_bid_greater_than_ask():

    validator = MarketDataValidator()

    data = create_data()

    data.bid = 101000

    data.ask = 100000

    assert not validator.validate(data)


def test_negative_volume():

    validator = MarketDataValidator()

    data = create_data()

    data.volume = -100

    assert not validator.validate(data)


def test_empty_symbol():

    validator = MarketDataValidator()

    data = create_data()

    data.symbol = ""

    assert not validator.validate(data)