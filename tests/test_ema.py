from src.analysis.technical.ema import EMAAnalyzer
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def test_calculate_ema():

    series = CandleSeries(
        symbol="BTC/USDT",
        timeframe="1h",
    )

    for i in range(1, 31):
        series.add(
            Candle(
                timestamp=i,
                open=i,
                high=i,
                low=i,
                close=i,
                volume=1000,
            )
        )

    ema = EMAAnalyzer.calculate(
        series,
        period=20,
    )

    assert ema is not None

    assert ema > 0


def test_price_above_ema():

    series = CandleSeries(
        symbol="BTC/USDT",
        timeframe="1h",
    )

    for i in range(1, 31):
        series.add(
            Candle(
                timestamp=i,
                open=i,
                high=i,
                low=i,
                close=i,
                volume=1000,
            )
        )

    assert EMAAnalyzer.is_above_ema(
        series,
        period=20,
    )