from src.analysis.ict.change_of_character import (
    ChangeOfCharacterAnalyzer,
)
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def bullish():

    candles = [

        Candle(1,100,105,99,104,100),
        Candle(2,104,106,102,105,100),
        Candle(3,105,107,103,104,100),
        Candle(4,104,105,101,102,100),
        Candle(5,102,103,99,100,100),
        Candle(6,106,112,105,111,100),

    ]

    return CandleSeries(
        symbol="BTCUSDT",
        timeframe="1m",
        candles=candles,
    )


def bearish():

    candles = [

        Candle(1,110,112,108,111,100),
        Candle(2,111,113,109,112,100),
        Candle(3,112,114,110,111,100),
        Candle(4,111,112,108,109,100),
        Candle(5,109,110,106,108,100),
        Candle(6,104,105,99,100,100),

    ]

    return CandleSeries(
        symbol="BTCUSDT",
        timeframe="1m",
        candles=candles,
    )


def test_bullish():

    signal = ChangeOfCharacterAnalyzer().analyze(
        bullish()
    )

    assert signal.direction == "BUY"


def test_bearish():

    signal = ChangeOfCharacterAnalyzer().analyze(
        bearish()
    )

    assert signal.direction == "SELL"