from src.analysis.technical.macd import MACDAnalyzer
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def create_series():

    series = CandleSeries(
        symbol="BTC/USDT",
        timeframe="1h",
    )

    price = 100

    for i in range(40):

        series.add(
            Candle(
                timestamp=i,
                open=price,
                high=price + 2,
                low=price - 2,
                close=price,
                volume=1000,
            )
        )

        price += 1

    return series


def test_macd():

    series = create_series()

    macd = MACDAnalyzer.calculate(series)

    assert macd is not None


def test_signal():

    series = create_series()

    signal = MACDAnalyzer.signal(series)

    assert signal in (
        "BULLISH",
        "BEARISH",
        "NEUTRAL",
    )


def test_score():

    series = create_series()

    score = MACDAnalyzer.score(series)

    assert 0 <= score <= 100