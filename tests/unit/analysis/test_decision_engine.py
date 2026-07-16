from src.analysis.decision_engine import DecisionEngine
from src.analysis.signal_engine import Signal


def test_buy():

    engine = DecisionEngine()

    signal = engine.decide(
        Signal(
            "BUY",
            90,
            "EMA",
        )
    )

    assert signal.direction == "BUY"


def test_low_confidence():

    engine = DecisionEngine()

    signal = engine.decide(
        Signal(
            "BUY",
            40,
            "EMA",
        )
    )

    assert signal.direction == "NEUTRAL"


def test_sell():

    engine = DecisionEngine()

    signal = engine.decide(
        Signal(
            "SELL",
            95,
            "MACD",
        )
    )

    assert signal.direction == "SELL"


def test_neutral():

    engine = DecisionEngine()

    signal = engine.decide(
        Signal(
            "NEUTRAL",
            0,
            "",
        )
    )

    assert signal.direction == "NEUTRAL"