from src.analysis.technical.rsi import RSIAnalyzer
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def create_series():

    series = CandleSeries(
        symbol="BTC/USDT",
        timeframe="1h",
    )

    prices = [
        44, 45, 46, 47, 48,
        49, 50, 49, 50, 51,
        52, 53, 54, 55, 56,
    ]

    for i, price in enumerate(prices):
        series.add(
            Candle(
                timestamp=i,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=1000,
            )
        )

    return series


def test_rsi():

    series = create_series()

    rsi = RSIAnalyzer.calculate(series)

    assert rsi is not None

    assert 0 <= rsi <= 100


def test_is_overbought():

    series = create_series()

    assert isinstance(
        RSIAnalyzer.is_overbought(series),
        bool,
    )


def test_is_oversold():

    series = create_series()

    assert isinstance(
        RSIAnalyzer.is_oversold(series),
        bool,
    )