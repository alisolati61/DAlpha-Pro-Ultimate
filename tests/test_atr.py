from src.analysis.technical.atr import ATRAnalyzer
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def create_series():

    series = CandleSeries(
        symbol="BTC/USDT",
        timeframe="1h",
    )

    prices = [
        (100, 105, 99, 103),
        (103, 107, 101, 106),
        (106, 110, 104, 108),
        (108, 111, 107, 110),
        (110, 114, 109, 113),
        (113, 116, 111, 115),
        (115, 118, 114, 117),
        (117, 121, 116, 120),
        (120, 123, 118, 121),
        (121, 125, 120, 124),
        (124, 127, 123, 126),
        (126, 129, 125, 128),
        (128, 132, 127, 131),
        (131, 135, 130, 134),
        (134, 138, 133, 137),
    ]

    for i, (o, h, l, c) in enumerate(prices):

        series.add(
            Candle(
                timestamp=i,
                open=o,
                high=h,
                low=l,
                close=c,
                volume=1000,
            )
        )

    return series


def test_atr():

    series = create_series()

    atr = ATRAnalyzer.calculate(series)

    assert atr is not None

    assert atr > 0


def test_volatility_score():

    series = create_series()

    score = ATRAnalyzer.volatility_score(series)

    assert 0 <= score <= 100