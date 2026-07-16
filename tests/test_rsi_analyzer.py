from src.intelligence.analyzers.rsi_analyzer import RSIScorer
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def test_rsi_score():

    series = CandleSeries(
        symbol="BTC/USDT",
        timeframe="1h",
    )

    prices = [
        44,45,46,47,48,
        49,50,49,50,51,
        52,53,54,55,56,
    ]

    for i, p in enumerate(prices):
        series.add(
            Candle(
                timestamp=i,
                open=p,
                high=p,
                low=p,
                close=p,
                volume=1000,
            )
        )

    score = RSIScorer.score(series)

    assert 0 <= score <= 100