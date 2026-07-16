from src.market.candle_mapper import CandleMapper


def test_mapper():

    raw = [
        [1, 100, 105, 95, 102, 1000],
        [2, 102, 108, 101, 107, 1200],
    ]

    series = CandleMapper.from_ohlcv(
        symbol="BTC/USDT",
        timeframe="1h",
        ohlcv=raw,
    )

    assert len(series) == 2

    assert series.last().close == 107

    assert series.last().volume == 1200