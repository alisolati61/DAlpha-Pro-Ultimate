from src.analysis.ict.ict_engine import (
    ICTEngine,
    ICTModule,
)
from src.analysis.signal_engine import Signal
from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


class DummyICT(ICTModule):

    def analyze(
        self,
        series: CandleSeries,
    ) -> Signal:

        return Signal(
            direction="BUY",
            confidence=90,
            reason="ICT Dummy",
        )


def build_series():

    candles = []

    for i in range(30):

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

    return CandleSeries(
        symbol="BTCUSDT",
        timeframe="1m",
        candles=candles,
    )


def test_register():

    engine = ICTEngine()

    engine.register(DummyICT())

    assert len(engine.modules()) == 1


def test_analyze():

    engine = ICTEngine()

    engine.register(DummyICT())

    signals = engine.analyze(build_series())

    assert len(signals) == 1

    assert signals[0].direction == "BUY"