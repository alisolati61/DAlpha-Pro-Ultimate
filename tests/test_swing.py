import pytest

from src.analysis.technical.swing import (
    SwingAnalyzer,
    SwingPoint,
)
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def create_series() -> CandleSeries:
    series = CandleSeries(
        symbol="BTC/USDT",
        timeframe="1h",
    )

    data = [
        (100, 101, 99, 100),
        (100, 103, 98, 102),
        (102, 108, 101, 107),
        (107, 104, 100, 103),
        (103, 101, 94, 98),
        (98, 99, 97, 97),
        (97, 103, 98, 102),
    ]

    for index, (open_, high, low, close) in enumerate(data):
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


def create_short_series() -> CandleSeries:
    series = CandleSeries(
        symbol="BTC/USDT",
        timeframe="1h",
    )

    series.add(
        Candle(
            timestamp=0,
            open=100,
            high=101,
            low=99,
            close=100,
            volume=1000,
        )
    )

    return series


def test_swing_highs() -> None:
    highs = SwingAnalyzer.highs(create_series())

    assert len(highs) == 1
    assert highs[0] == SwingPoint(
        index=2,
        price=108,
        kind="HIGH",
    )


def test_swing_lows() -> None:
    lows = SwingAnalyzer.lows(create_series())

    assert len(lows) == 1
    assert lows[0] == SwingPoint(
        index=4,
        price=94,
        kind="LOW",
    )


def test_latest_high() -> None:
    latest = SwingAnalyzer.latest_high(create_series())

    assert latest is not None
    assert latest.index == 2
    assert latest.price == 108
    assert latest.kind == "HIGH"


def test_latest_low() -> None:
    latest = SwingAnalyzer.latest_low(create_series())

    assert latest is not None
    assert latest.index == 4
    assert latest.price == 94
    assert latest.kind == "LOW"


def test_returns_empty_highs_when_data_is_insufficient() -> None:
    assert SwingAnalyzer.highs(create_short_series()) == []


def test_returns_empty_lows_when_data_is_insufficient() -> None:
    assert SwingAnalyzer.lows(create_short_series()) == []


def test_latest_high_returns_none_when_data_is_insufficient() -> None:
    assert SwingAnalyzer.latest_high(create_short_series()) is None


def test_latest_low_returns_none_when_data_is_insufficient() -> None:
    assert SwingAnalyzer.latest_low(create_short_series()) is None


@pytest.mark.parametrize("lookback", [0, -1, -10])
def test_rejects_non_positive_lookback(lookback: int) -> None:
    with pytest.raises(
        ValueError,
        match="lookback must be greater than zero",
    ):
        SwingAnalyzer.highs(
            create_series(),
            lookback=lookback,
        )


@pytest.mark.parametrize("lookback", [1.5, "2", None, True])
def test_rejects_invalid_lookback(lookback: object) -> None:
    with pytest.raises(
        TypeError,
        match="lookback must be an integer",
    ):
        SwingAnalyzer.highs(
            create_series(),
            lookback=lookback,  # type: ignore[arg-type]
        )


def test_rejects_invalid_series() -> None:
    with pytest.raises(
        TypeError,
        match="series must be a CandleSeries instance",
    ):
        SwingAnalyzer.highs(
            None,  # type: ignore[arg-type]
        )


def test_custom_lookback() -> None:
    highs = SwingAnalyzer.highs(
        create_series(),
        lookback=1,
    )
    lows = SwingAnalyzer.lows(
        create_series(),
        lookback=1,
    )

    assert any(point.index == 2 for point in highs)
    assert any(point.index == 4 for point in lows)


def test_swing_point_is_immutable() -> None:
    point = SwingPoint(
        index=2,
        price=108,
        kind="HIGH",
    )

    with pytest.raises(AttributeError):
        point.price = 110  # type: ignore[misc]