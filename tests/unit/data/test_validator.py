from datetime import UTC, datetime

from src.data.market_data import MarketData
from src.data.validator import (
    MarketDataValidator,
    ValidationResult,
)


def make():

    return MarketData(

        symbol="BTCUSDT",

        exchange="Binance",

        timeframe="1m",

        price=100,

        bid=99,

        ask=101,

        volume=10,

        timestamp=datetime.now(UTC),

    )


def test_valid():

    validator = MarketDataValidator()

    result = validator.validate(

        make(),

    )

    assert isinstance(

        result,

        ValidationResult,

    )

    assert result.valid


def test_price():

    validator = MarketDataValidator()

    d = make()

    d.price = 0

    assert not validator.validate(d).valid


def test_bid():

    validator = MarketDataValidator()

    d = make()

    d.bid = 0

    assert not validator.validate(d).valid


def test_ask():

    validator = MarketDataValidator()

    d = make()

    d.ask = 0

    assert not validator.validate(d).valid


def test_bid_ask():

    validator = MarketDataValidator()

    d = make()

    d.bid = 110

    d.ask = 100

    assert not validator.validate(d).valid


def test_volume():

    validator = MarketDataValidator()

    d = make()

    d.volume = -1

    assert not validator.validate(d).valid


def test_types():

    validator = MarketDataValidator()

    result = validator.validate(

        make(),

    )

    assert isinstance(

        result.valid,

        bool,

    )

    assert isinstance(

        result.reason,

        str,

    )