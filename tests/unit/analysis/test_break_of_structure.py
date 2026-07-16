from src.analysis.ict.break_of_structure import BreakOfStructureAnalyzer
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def bullish_series():

    candles = [

        Candle(1,100,105,99,104,100),

        Candle(2,104,106,102,105,100),

        Candle(3,105,107,103,106,100),

        Candle(4,106,108,104,107,100),

        Candle(5,108,112,107,111,100),

    ]

    return CandleSeries(

        symbol="BTCUSDT",

        timeframe="1m",

        candles=candles,

    )


def bearish_series():

    candles = [

        Candle(1,100,105,99,104,100),

        Candle(2,104,106,102,103,100),

        Candle(3,103,104,98,99,100),

        Candle(4,99,100,95,96,100),

        Candle(5,96,97,90,91,100),

    ]

    return CandleSeries(

        symbol="BTCUSDT",

        timeframe="1m",

        candles=candles,

    )


def test_bullish():

    signal = BreakOfStructureAnalyzer().analyze(

        bullish_series()

    )

    assert signal.direction == "BUY"


def test_bearish():

    signal = BreakOfStructureAnalyzer().analyze(

        bearish_series()

    )

    assert signal.direction == "SELL"