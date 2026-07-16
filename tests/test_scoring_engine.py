from src.core.scoring_engine import ScoringEngine


def test_scoring_engine():
    engine = ScoringEngine()

    signals = {
        "trend": 15,
        "volume": 10,
        "onchain": 10,
        "orderflow": 15,
        "sentiment": 10,
        "risk": 5,
    }

    result = engine.calculate(signals)

    assert isinstance(result, dict)
    assert "trend" in result
    assert "volume" in result
    assert "onchain" in result
    assert "orderflow" in result
    assert "sentiment" in result
    assert "risk" in result