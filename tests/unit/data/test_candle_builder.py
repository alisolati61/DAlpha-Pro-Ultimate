from datetime import datetime

from src.data.candle_builder import CandleBuilder


def test_start():

    builder = CandleBuilder()

    candle = builder.start(
        symbol="BTCUSDT",
        timeframe="1m",
        price=100000,
        volume=5,
        timestamp=datetime.now(),
    )

    assert candle.open == 100000
    assert candle.high == 100000
    assert candle.low == 100000
    assert candle.close == 100000
    assert candle.volume == 5


def test_update():

    builder = CandleBuilder()

    builder.start(
        symbol="BTCUSDT",
        timeframe="1m",
        price=100000,
        volume=5,
        timestamp=datetime.now(),
    )

    candle = builder.update(
        price=101000,
        volume=2,
    )

    assert candle.high == 101000
    assert candle.low == 100000
    assert candle.close == 101000
    assert candle.volume == 7


def test_update_lower_price():

    builder = CandleBuilder()

    builder.start(
        symbol="BTCUSDT",
        timeframe="1m",
        price=100000,
        volume=5,
        timestamp=datetime.now(),
    )

    candle = builder.update(
        price=99000,
        volume=1,
    )

    assert candle.low == 99000
    assert candle.close == 99000