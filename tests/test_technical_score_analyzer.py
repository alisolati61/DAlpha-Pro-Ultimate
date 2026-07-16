from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries
from src.intelligence.analyzers.technical_score_analyzer import (
    TechnicalScoreAnalyzer,
)


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


def test_score():

    series = create_series()

    score = TechnicalScoreAnalyzer.score(series)

    assert 0 <= score <= 100