from src.analysis.signal_engine import Signal
from src.strategy.strategy_engine import (
    BaseStrategy,
    StrategyEngine,
)


class DummyStrategy(BaseStrategy):

    def generate_signal(self):

        return Signal(
            direction="BUY",
            confidence=90,
            reason="Dummy",
        )


def test_register():

    engine = StrategyEngine()

    engine.register(DummyStrategy())

    assert len(engine.strategies()) == 1


def test_run():

    engine = StrategyEngine()

    engine.register(DummyStrategy())

    signals = engine.run()

    assert len(signals) == 1

    assert signals[0].direction == "BUY"