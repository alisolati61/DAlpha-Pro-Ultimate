from src.ai.ai_engine import (
    AIEngine,
    AIInput,
)


def valid_scores():

    return {
        "trend": 15,
        "smc": 20,
        "orderflow": 15,
        "risk": 10,
    }


def invalid_scores():

    return {
        "trend": 5,
        "smc": 20,
        "orderflow": 5,
        "risk": 2,
    }


def test_ai_engine_valid_signal():

    engine = AIEngine()

    result = engine.evaluate(
        AIInput(
            scores=valid_scores(),
            final_score=82,
            confidence=0.85,
            trend_score=80,
            volatility_score=40,
            volume_score=60,
            momentum_score=70,
        )
    )

    assert result.valid is True
    assert result.probability > 0
    assert result.confidence > 0
    assert isinstance(result.market_regime, str)


def test_ai_engine_invalid_signal():

    engine = AIEngine()

    result = engine.evaluate(
        AIInput(
            scores=invalid_scores(),
            final_score=30,
            confidence=0.40,
            trend_score=20,
            volatility_score=40,
            volume_score=40,
            momentum_score=30,
        )
    )

    assert result.valid is False
    assert result.probability == 0.0


def test_ai_engine_bull_market():

    engine = AIEngine()

    result = engine.evaluate(
        AIInput(
            scores=valid_scores(),
            final_score=90,
            confidence=0.90,
            trend_score=90,
            volatility_score=30,
            volume_score=70,
            momentum_score=70,
        )
    )

    assert result.market_regime == "bull"


def test_ai_engine_bear_market():

    engine = AIEngine()

    result = engine.evaluate(
        AIInput(
            scores=valid_scores(),
            final_score=80,
            confidence=0.80,
            trend_score=15,
            volatility_score=30,
            volume_score=60,
            momentum_score=40,
        )
    )

    assert result.market_regime == "bear"


def test_ai_engine_sideways_market():

    engine = AIEngine()

    result = engine.evaluate(
        AIInput(
            scores=valid_scores(),
            final_score=75,
            confidence=0.80,
            trend_score=50,
            volatility_score=40,
            volume_score=50,
            momentum_score=50,
        )
    )

    assert result.market_regime == "sideways"


def test_probability_range():

    engine = AIEngine()

    result = engine.evaluate(
        AIInput(
            scores=valid_scores(),
            final_score=95,
            confidence=0.95,
            trend_score=90,
            volatility_score=20,
            volume_score=90,
            momentum_score=90,
        )
    )

    assert 0 <= result.probability <= 100


def test_ai_engine_output_types():

    engine = AIEngine()

    result = engine.evaluate(
        AIInput(
            scores=valid_scores(),
            final_score=85,
            confidence=0.80,
            trend_score=80,
            volatility_score=35,
            volume_score=65,
            momentum_score=75,
        )
    )

    assert isinstance(result.valid, bool)
    assert isinstance(result.probability, float)
    assert isinstance(result.confidence, float)
    assert isinstance(result.market_regime, str)
    assert isinstance(result.explanation, str)