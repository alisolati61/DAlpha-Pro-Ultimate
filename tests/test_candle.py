from src.domain.candle import Candle


def test_create_candle():

    candle = Candle(
        timestamp=123456789,
        open=100,
        high=105,
        low=95,
        close=102,
        volume=10000,
    )

    assert candle.close == 102

    assert candle.high == 105

    assert candle.low == 95