from src.analysis.ict.breaker_block import BreakerBlockAnalyzer
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def bullish():

    candles = [

        Candle(1,100,102,99,101,100),
        Candle(2,101,103,100,102,100),
        Candle(3,102,104,101,103,100),
        Candle(4,103,105,102,104,100),
        Candle(5,104,106,103,105,100),
        Candle(6,105,107,104,106,100),
        Candle(7,108,111,108,110,100),

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
        Candle(7,109,110,104,105,100),

    ]

    return CandleSeries(
        symbol="BTCUSDT",
        timeframe="1m",
        candles=candles,
    )


def test_buy():

    signal = BreakerBlockAnalyzer().analyze(
        bullish()
    )

    assert signal.direction == "BUY"


def test_sell():

    signal = BreakerBlockAnalyzer().analyze(
        bearish()
    )

    assert signal.direction == "SELL"