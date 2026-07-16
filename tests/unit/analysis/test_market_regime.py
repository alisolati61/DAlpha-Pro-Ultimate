from src.analysis.market_regime import (
    MarketRegime,
    MarketRegimeEngine,
)
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


def build_series(start, step):

    candles = []

    price = start

    for i in range(20):

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

        price += step

    return CandleSeries(
        symbol="BTCUSDT",
        timeframe="1m",
        candles=candles,
    )


def test_uptrend():

    regime = MarketRegimeEngine().detect(
        build_series(100, 2)
    )

    assert regime == MarketRegime.TRENDING_UP


def test_downtrend():

    regime = MarketRegimeEngine().detect(
        build_series(200, -2)
    )

    assert regime == MarketRegime.TRENDING_DOWN


def test_range():

    candles = []

    for i in range(20):

        candles.append(
            Candle(
                timestamp=i,
                open=100,
                high=101,
                low=99,
                close=100,
                volume=100,
            )
        )

    series = CandleSeries(
        symbol="BTCUSDT",
        timeframe="1m",
        candles=candles,
    )

    regime = MarketRegimeEngine().detect(series)

    assert regime == MarketRegime.RANGING