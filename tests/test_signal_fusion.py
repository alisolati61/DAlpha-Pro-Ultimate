from src.decision import (
    DecisionInput,
    SignalFusion,
)


def test_signal_fusion():

    decision = DecisionInput(
        technical_score=90,
        smart_money_score=80,
        orderflow_score=70,
        sentiment_score=60,
        onchain_score=50,
    )

    scores = SignalFusion.fuse(decision)

    assert scores["technical"] == 90
    assert scores["smart_money"] == 80
    assert scores["orderflow"] == 70
    assert scores["sentiment"] == 60
    assert scores["onchain"] == 50


def test_average():

    scores = {
        "technical": 100,
        "smart_money": 80,
        "orderflow": 60,
        "sentiment": 40,
        "onchain": 20,
    }

    # Weighted Average:
    # 100×0.25 + 80×0.30 + 60×0.20 + 40×0.10 + 20×0.15 = 68

    assert SignalFusion.average(scores) == 68.0


def test_average_empty():

    assert SignalFusion.average({}) == 0.0