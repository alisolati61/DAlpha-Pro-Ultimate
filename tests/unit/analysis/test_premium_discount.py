from src.analysis.ict.premium_discount import PremiumDiscountAnalyzer
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def build_discount():

    candles = []

    for i in range(20):

        candles.append(

            Candle(
                timestamp=i,
                open=100,
                high=120,
                low=80,
                close=85,
                volume=100,
            )

        )

    return CandleSeries(
        symbol="BTCUSDT",
        timeframe="1m",
        candles=candles,
    )


def build_premium():

    candles = []

    for i in range(20):

        candles.append(

            Candle(
                timestamp=i,
                open=100,
                high=120,
                low=80,
                close=115,
                volume=100,
            )

        )

    return CandleSeries(
        symbol="BTCUSDT",
        timeframe="1m",
        candles=candles,
    )


def test_discount():

    signal = PremiumDiscountAnalyzer().analyze(
        build_discount()
    )

    assert signal.direction == "BUY"


def test_premium():

    signal = PremiumDiscountAnalyzer().analyze(
        build_premium()
    )

    assert signal.direction == "SELL"