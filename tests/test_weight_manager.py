from src.decision import WeightManager


def test_default_weights():

    weights = WeightManager.weights()

    assert weights["technical"] == 0.25
    assert weights["smart_money"] == 0.30
    assert weights["orderflow"] == 0.20
    assert weights["sentiment"] == 0.10
    assert weights["onchain"] == 0.15


def test_weighted_average():

    scores = {
        "technical": 100,
        "smart_money": 100,
        "orderflow": 100,
        "sentiment": 100,
        "onchain": 100,
    }

    assert WeightManager.weighted_average(scores) == 100


def test_empty_scores():

    assert WeightManager.weighted_average({}) == 0.0