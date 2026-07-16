from src.analysis.ict.mitigation_block import MitigationBlockAnalyzer
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def bullish():

    candles = [

        Candle(1,100,102,99,101,100),
        Candle(2,101,103,100,102,100),
        Candle(3,102,104,101,103,100),
        Candle(4,103,105,102,104,100),
        Candle(5,104,106,103,105,100),
        Candle(6,106,108,104,107,100),
        Candle(7,105,109,103,108,100),

    ]

    return CandleSeries(
        symbol="BTCUSDT",
        timeframe="1m",
        candles=candles,
    )


def bearish():

    candles = [

        Candle(1,110,112,109,111,100),
        Candle(2,111,113,110,112,100),
        Candle(3,112,114,111,113,100),
        Candle(4,113,115,112,114,100),
        Candle(5,114,116,113,115,100),
        Candle(6,115,117,114,116,100),
        Candle(7,116,118,112,113,100),

    ]

    return CandleSeries(
        symbol="BTCUSDT",
        timeframe="1m",
        candles=candles,
    )


def test_buy():

    signal = MitigationBlockAnalyzer().analyze(
        bullish()
    )

    assert signal.direction == "BUY"


def test_sell():

    signal = MitigationBlockAnalyzer().analyze(
        bearish()
    )

    assert signal.direction == "SELL"