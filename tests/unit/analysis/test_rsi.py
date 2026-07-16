from src.analysis.technical.rsi import RSIAnalyzer
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def build_series():

    candles = []

    price = 100

    for i in range(30):

        candles.append(
            Candle(
                timestamp=i,
                open=price,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=100,
            )
        )

        price += 1

    return CandleSeries(
        symbol="BTCUSDT",
        timeframe="1m",
        candles=candles,
    )


def test_rsi():

    series = build_series()

    value = RSIAnalyzer.calculate(series)

    assert value is not None

    assert value > 70


def test_overbought():

    series = build_series()

    assert RSIAnalyzer.is_overbought(series)


def test_not_oversold():

    series = build_series()

    assert not RSIAnalyzer.is_oversold(series)