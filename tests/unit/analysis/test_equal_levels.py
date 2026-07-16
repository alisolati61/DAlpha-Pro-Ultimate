from src.analysis.ict.equal_levels import EqualLevelsAnalyzer
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def equal_highs():

    candles = [

        Candle(1,100,110,99,105,100),
        Candle(2,101,110,100,106,100),
        Candle(3,102,110,101,107,100),
        Candle(4,103,110,102,108,100),
        Candle(5,104,110,103,109,100),
        Candle(6,105,110,104,108,100),

    ]

    return CandleSeries(

        symbol="BTCUSDT",

        timeframe="1m",

        candles=candles,

    )


def equal_lows():

    candles = [

        Candle(1,100,105,90,101,100),
        Candle(2,101,106,90,102,100),
        Candle(3,102,107,90,103,100),
        Candle(4,103,108,90,104,100),
        Candle(5,104,109,90,105,100),
        Candle(6,105,110,90,106,100),

    ]

    return CandleSeries(

        symbol="BTCUSDT",

        timeframe="1m",

        candles=candles,

    )


def test_equal_highs():

    signal = EqualLevelsAnalyzer().analyze(

        equal_highs()

    )

    assert signal.direction == "SELL"


def test_equal_lows():

    signal = EqualLevelsAnalyzer().analyze(

        equal_lows()

    )

    assert signal.direction == "BUY"