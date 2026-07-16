from src.analysis.technical.swing import SwingAnalyzer
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def create_series():

    series = CandleSeries(
        symbol="BTC/USDT",
        timeframe="1h",
    )

    data = [
    (100, 101, 99, 100),
    (100, 103, 98, 102),
    (102, 108, 101, 107),
    (107, 104, 100, 103),
    (103, 101, 94, 98),
    (98, 99, 97, 97),
    (97, 103, 98, 102),
]

    for i, (o, h, l, c) in enumerate(data):

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


def test_swing_highs():

    series = create_series()

    highs = SwingAnalyzer.highs(series)

    assert len(highs) >= 1

    assert highs[0].kind == "HIGH"


def test_swing_lows():

    series = create_series()

    lows = SwingAnalyzer.lows(series)

    assert len(lows) >= 1

    assert lows[0].kind == "LOW"