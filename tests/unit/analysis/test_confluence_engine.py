from src.analysis.confluence_engine import ConfluenceEngine
from src.analysis.signal_engine import Signal


def test_buy():

    engine = ConfluenceEngine()

    signal = engine.combine(
        [
            Signal("BUY", 90, "EMA"),
            Signal("BUY", 80, "RSI"),
            Signal("SELL", 20, "ATR"),
        ]
    )

    assert signal.direction == "BUY"


def test_sell():

    engine = ConfluenceEngine()

    signal = engine.combine(
        [
            Signal("SELL", 90, "EMA"),
            Signal("SELL", 80, "MACD"),
        ]
    )

    assert signal.direction == "SELL"


def test_conflict():

    engine = ConfluenceEngine()

    signal = engine.combine(
        [
            Signal("BUY", 50, "EMA"),
            Signal("SELL", 50, "RSI"),
        ]
    )

    assert signal.direction == "NEUTRAL"


def test_empty():

    engine = ConfluenceEngine()

    signal = engine.combine([])

    assert signal.direction == "NEUTRAL"