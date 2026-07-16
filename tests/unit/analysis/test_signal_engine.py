from src.analysis.signal_engine import SignalEngine


def test_buy():

    engine = SignalEngine()

    signal = engine.bullish(
        confidence=90,
        reason="EMA Cross",
    )

    assert signal.direction == "BUY"
    assert signal.confidence == 90


def test_sell():

    engine = SignalEngine()

    signal = engine.bearish(
        confidence=80,
        reason="MACD",
    )

    assert signal.direction == "SELL"


def test_neutral():

    engine = SignalEngine()

    signal = engine.neutral()

    assert signal.direction == "NEUTRAL"