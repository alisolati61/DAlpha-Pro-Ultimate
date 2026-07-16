from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def test_add_candle():

    series = CandleSeries(
        symbol="BTC/USDT",
        timeframe="1h",
    )

    candle = Candle(
        timestamp=1,
        open=100,
        high=105,
        low=95,
        close=102,
        volume=1000,
    )

    series.add(candle)

    assert len(series) == 1

    assert series.last() == candle