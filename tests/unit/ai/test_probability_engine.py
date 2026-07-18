from src.ai.market_regime import (
    MarketContext,
    MarketRegimeAnalyzer,
)
from src.ai.probability_engine import (
    ProbabilityEngine,
    ProbabilityInput,
)


def build_regime(
    trend: float = 80,
    volatility: float = 30,
    volume: float = 50,
    momentum: float = 50,
):
    analyzer = MarketRegimeAnalyzer()

    return analyzer.analyze(
        MarketContext(
            trend_score=trend,
            volatility_score=volatility,
            volume_score=volume,
            momentum_score=momentum,
        )
    )


def test_probability_bull_market():

    engine = ProbabilityEngine()

    result = engine.estimate(
        ProbabilityInput(
            final_score=80,
            confidence=0.80,
            regime=build_regime(),
        )
    )

    assert result.probability > 0
    assert result.confidence == 0.80


def test_probability_bear_market():

    engine = ProbabilityEngine()

    regime = build_regime(
        trend=10,
    )

    result = engine.estimate(
        ProbabilityInput(
            final_score=80,
            confidence=0.80,
            regime=regime,
        )
    )

    assert result.probability > 0


def test_probability_high_volatility():

    engine = ProbabilityEngine()

    regime = build_regime(
        trend=50,
        volatility=95,
    )

    result = engine.estimate(
        ProbabilityInput(
            final_score=80,
            confidence=0.80,
            regime=regime,
        )
    )

    assert result.probability >= 0


def test_probability_never_exceeds_100():

    engine = ProbabilityEngine()

    result = engine.estimate(
        ProbabilityInput(
            final_score=500,
            confidence=10,
            regime=build_regime(),
        )
    )

    assert result.probability <= 100


def test_probability_never_negative():

    engine = ProbabilityEngine()

    result = engine.estimate(
        ProbabilityInput(
            final_score=-100,
            confidence=1,
            regime=build_regime(),
        )
    )

    assert result.probability >= 0


def test_probability_explanation():

    engine = ProbabilityEngine()

    result = engine.estimate(
        ProbabilityInput(
            final_score=70,
            confidence=0.75,
            regime=build_regime(),
        )
    )

    assert isinstance(result.explanation, str)

    assert len(result.explanation) > 0


def test_probability_result_types():

    engine = ProbabilityEngine()

    result = engine.estimate(
        ProbabilityInput(
            final_score=75,
            confidence=0.85,
            regime=build_regime(),
        )
    )

    assert isinstance(result.probability, float)

    assert isinstance(result.confidence, float)

    assert isinstance(result.explanation, str)