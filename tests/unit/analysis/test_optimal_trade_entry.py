from src.analysis.ict.optimal_trade_entry import (
    OptimalTradeEntryAnalyzer,
)
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def bullish():

    candles = []

    for i in range(20):

        candles.append(

            Candle(
                timestamp=i,
                open=100,
                high=120,
                low=80,
                close=90,
                volume=100,
            )

        )

    return CandleSeries(
        symbol="BTCUSDT",
        timeframe="1m",
        candles=candles,
    )


def bearish():

    candles = []

    for i in range(20):

        candles.append(

            Candle(
                timestamp=i,
                open=100,
                high=120,
                low=80,
                close=110,
                volume=100,
            )

        )

    return CandleSeries(
        symbol="BTCUSDT",
        timeframe="1m",
        candles=candles,
    )


def test_buy():

    signal = OptimalTradeEntryAnalyzer().analyze(
        bullish()
    )

    assert signal.direction == "BUY"


def test_sell():

    signal = OptimalTradeEntryAnalyzer().analyze(
        bearish()
    )

    assert signal.direction == "SELL"