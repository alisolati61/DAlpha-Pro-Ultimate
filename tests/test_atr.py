import pytest

from src.analysis.technical.atr import ATRAnalyzer
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def create_series() -> CandleSeries:
    series = CandleSeries(
        symbol="BTC/USDT",
        timeframe="1h",
    )

    prices = [
        (100, 105, 99, 103),
        (103, 107, 101, 106),
        (106, 110, 104, 108),
        (108, 111, 107, 110),
        (110, 114, 109, 113),
        (113, 116, 111, 115),
        (115, 118, 114, 117),
        (117, 121, 116, 120),
        (120, 123, 118, 121),
        (121, 125, 120, 124),
        (124, 127, 123, 126),
        (126, 129, 125, 128),
        (128, 132, 127, 131),
        (131, 135, 130, 134),
        (134, 138, 133, 137),
    ]

    for index, (open_, high, low, close) in enumerate(prices):
        series.add(
            Candle(
                timestamp=index,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=1000,
            )
        )

    return series


def test_atr() -> None:
    atr = ATRAnalyzer.calculate(create_series())

    assert atr is not None
    assert atr > 0


def test_atr_returns_none_when_data_is_insufficient() -> None:
    series = create_series()

    assert ATRAnalyzer.calculate(series, period=15) is None


def test_atr_rejects_zero_period() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        ATRAnalyzer.calculate(create_series(), period=0)


def test_atr_rejects_negative_period() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        ATRAnalyzer.calculate(create_series(), period=-1)


def test_atr_rejects_non_integer_period() -> None:
    with pytest.raises(TypeError, match="integer"):
        ATRAnalyzer.calculate(create_series(), period=14.5)


def test_volatility_score() -> None:
    score = ATRAnalyzer.volatility_score(create_series())

    assert 0 <= score <= 100


def test_volatility_score_returns_neutral_when_data_is_insufficient() -> None:
    series = CandleSeries(
        symbol="BTC/USDT",
        timeframe="1h",
    )

    assert ATRAnalyzer.volatility_score(series) == 50.0