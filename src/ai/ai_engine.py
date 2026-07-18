from __future__ import annotations

from dataclasses import dataclass

from src.ai.feedback_loop import FeedbackLoop
from src.ai.market_regime import (
    MarketContext,
    MarketRegimeAnalyzer,
)
from src.ai.performance_tracker import PerformanceTracker
from src.ai.probability_engine import (
    ProbabilityEngine,
    ProbabilityInput,
)
from src.ai.signal_validation import SignalValidationEngine
from src.ai.weight_optimizer import WeightOptimizer


@dataclass(slots=True)
class AIInput:
    """
    Complete AI input.
    """

    scores: dict[str, float]

    final_score: float

    confidence: float

    trend_score: float

    volatility_score: float

    volume_score: float

    momentum_score: float


@dataclass(slots=True)
class AIResult:
    """
    Final AI output.
    """

    valid: bool

    probability: float

    confidence: float

    market_regime: str

    explanation: str


class AIEngine:
    """
    DAlpha Ultimate AI Engine.

    Pipeline

        Signal Validation
                ↓
        Market Regime
                ↓
        Probability
                ↓
        Decision

    Future

    - LLM Advisor
    - Reinforcement Learning
    - Bayesian Layer
    - Online Learning
    """

    def __init__(self) -> None:

        self.performance_tracker = PerformanceTracker()

        self.feedback_loop = FeedbackLoop()

        self.weight_optimizer = WeightOptimizer()

        self.signal_validation = SignalValidationEngine()

        self.market_regime = MarketRegimeAnalyzer()

        self.probability = ProbabilityEngine(
            optimizer=self.weight_optimizer,
        )

    # --------------------------------------------------

    def evaluate(
        self,
        data: AIInput,
    ) -> AIResult:

        validation = self.signal_validation.validate(
            data.scores,
        )

        if not validation.valid:

            return AIResult(
                valid=False,
                probability=0.0,
                confidence=0.0,
                market_regime="unknown",
                explanation=validation.reason,
            )

        regime = self.market_regime.analyze(
            MarketContext(
                trend_score=data.trend_score,
                volatility_score=data.volatility_score,
                volume_score=data.volume_score,
                momentum_score=data.momentum_score,
            )
        )

        probability = self.probability.estimate(
            ProbabilityInput(
                final_score=data.final_score,
                confidence=data.confidence,
                regime=regime,
            )
        )

        return AIResult(
            valid=True,
            probability=probability.probability,
            confidence=probability.confidence,
            market_regime=regime.regime.value,
            explanation=probability.explanation,
        )