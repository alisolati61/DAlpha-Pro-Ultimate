from src.analysis.technical.macd import MACDAnalyzer
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def build_series():

    candles = []

    price = 100

    for i in range(60):

        candles.append(
            Candle(
                timestamp=i,
                open=price,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=100,
            )
        )

        price += 1

    return CandleSeries(
        symbol="BTCUSDT",
        timeframe="1m",
        candles=candles,
    )


def test_macd():

    result = MACDAnalyzer.calculate(build_series())

    assert result is not None


def test_trend():

    trend = MACDAnalyzer.trend(build_series())

    assert trend in (
        "BULLISH",
        "BEARISH",
        "NEUTRAL",
    )


def test_score():

    score = MACDAnalyzer.score(build_series())

    assert 0 <= score <= 100