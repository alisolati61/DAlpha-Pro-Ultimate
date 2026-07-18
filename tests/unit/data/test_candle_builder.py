from src.data.candle_builder import (
    Candle,
    CandleBuilder,
)


def test_first_tick():

    builder = CandleBuilder()

    candle = builder.update(

        "BTCUSDT",

        "1m",

        100,

        5,

    )

    assert isinstance(

        candle,

        Candle,

    )

    assert candle.open == 100

    assert candle.close == 100


def test_high_low():

    builder = CandleBuilder()

    builder.update(

        "BTCUSDT",

        "1m",

        100,

        1,

    )

    candle = builder.update(

        "BTCUSDT",

        "1m",

        120,

        2,

    )

    assert candle.high == 120

    assert candle.low == 100


def test_close():

    builder = CandleBuilder()

    builder.update(

        "BTCUSDT",

        "1m",

        100,

        1,

    )

    candle = builder.update(

        "BTCUSDT",

        "1m",

        110,

        1,

    )

    assert candle.close == 110


def test_volume():

    builder = CandleBuilder()

    builder.update(

        "BTCUSDT",

        "1m",

        100,

        2,

    )

    candle = builder.update(

        "BTCUSDT",

        "1m",

        101,

        3,

    )

    assert candle.volume == 5


def test_latest():

    builder = CandleBuilder()

    builder.update(

        "BTCUSDT",

        "1m",

        100,

        1,

    )

    candle = builder.latest(

        "BTCUSDT",

        "1m",

    )

    assert candle is not None


def test_clear():

    builder = CandleBuilder()

    builder.update(

        "BTCUSDT",

        "1m",

        100,

        1,

    )

    builder.clear()

    assert builder.latest(

        "BTCUSDT",

        "1m",

    ) is None


def test_types():

    builder = CandleBuilder()

    candle = builder.update(

        "BTCUSDT",

        "1m",

        100,

        1,

    )

    assert isinstance(

        candle.open,

        float,

    )

    assert isinstance(

        candle.volume,

        float,

    )