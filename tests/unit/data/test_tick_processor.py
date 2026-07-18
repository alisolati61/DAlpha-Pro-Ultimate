from src.data.tick_processor import (
    Tick,
    TickProcessor,
)


def test_process():

    processor = TickProcessor()

    tick = processor.process(

        symbol="BTCUSDT",

        price=100,

        volume=5,

    )

    assert isinstance(
        tick,
        Tick,
    )


def test_latest():

    processor = TickProcessor()

    processor.process(

        "BTCUSDT",

        100,

        5,

    )

    tick = processor.latest(
        "BTCUSDT",
    )

    assert tick is not None

    assert tick.price == 100.0


def test_processed_counter():

    processor = TickProcessor()

    processor.process("BTCUSDT", 1, 1)

    processor.process("BTCUSDT", 2, 1)

    assert processor.processed_ticks == 2


def test_clear():

    processor = TickProcessor()

    processor.process("BTCUSDT", 1, 1)

    processor.clear()

    assert processor.processed_ticks == 0

    assert processor.latest("BTCUSDT") is None


def test_types():

    processor = TickProcessor()

    tick = processor.process(

        "BTCUSDT",

        100,

        5,

    )

    assert isinstance(
        tick.price,
        float,
    )

    assert isinstance(
        tick.volume,
        float,
    )


def test_multiple_symbols():

    processor = TickProcessor()

    processor.process("BTCUSDT", 100, 1)

    processor.process("ETHUSDT", 50, 2)

    assert processor.latest("BTCUSDT").price == 100

    assert processor.latest("ETHUSDT").price == 50