from src.analysis.ict.fair_value_gap import FairValueGapAnalyzer
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def build_bullish():

    candles = [

        Candle(1, 100, 105, 99, 104, 100),

        Candle(2, 104, 110, 103, 109, 100),

        Candle(3, 111, 115, 111, 114, 100),

    ]

    return CandleSeries(

        symbol="BTCUSDT",

        timeframe="1m",

        candles=candles,

    )


def build_neutral():

    candles = [

        Candle(1, 100, 105, 99, 104, 100),

        Candle(2, 104, 106, 101, 103, 100),

        Candle(3, 102, 104, 100, 103, 100),

    ]

    return CandleSeries(

        symbol="BTCUSDT",

        timeframe="1m",

        candles=candles,

    )


def test_bullish_fvg():

    analyzer = FairValueGapAnalyzer()

    signal = analyzer.analyze(build_bullish())

    assert signal.direction == "BUY"


def test_no_fvg():

    analyzer = FairValueGapAnalyzer()

    signal = analyzer.analyze(build_neutral())

    assert signal.direction == "NEUTRAL"