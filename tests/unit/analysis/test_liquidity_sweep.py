from src.analysis.ict.liquidity_sweep import LiquiditySweepAnalyzer
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def buy_signal():

    candles = [

        Candle(1,100,102,99,101,100),
        Candle(2,101,103,100,102,100),
        Candle(3,102,104,101,103,100),
        Candle(4,103,105,102,104,100),
        Candle(5,104,106,103,105,100),
        Candle(6,102,105,101,104,100),

    ]

    return CandleSeries(
        symbol="BTCUSDT",
        timeframe="1m",
        candles=candles,
    )


def sell_signal():

    candles = [

        Candle(1,100,102,99,101,100),
        Candle(2,101,103,100,102,100),
        Candle(3,102,104,101,103,100),
        Candle(4,103,105,102,104,100),
        Candle(5,104,106,103,105,100),
        Candle(6,105,107,104,105,100),

    ]

    return CandleSeries(
        symbol="BTCUSDT",
        timeframe="1m",
        candles=candles,
    )


def test_buy():

    signal = LiquiditySweepAnalyzer().analyze(
        buy_signal()
    )

    assert signal.direction == "BUY"


def test_sell():

    signal = LiquiditySweepAnalyzer().analyze(
        sell_signal()
    )

    assert signal.direction == "SELL"