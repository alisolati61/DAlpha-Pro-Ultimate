from __future__ import annotations

from dataclasses import dataclass

from src.ai.market_regime import MarketRegimeResult
from src.ai.weight_optimizer import WeightOptimizer


@dataclass(slots=True)
class ProbabilityInput:
    """
    Inputs required for probability estimation.
    """

    final_score: float
    confidence: float
    regime: MarketRegimeResult


@dataclass(slots=True)
class ProbabilityResult:
    """
    Final probability estimation.
    """

    probability: float
    confidence: float
    explanation: str


class ProbabilityEngine:
    """
    AI Probability Engine.

    Responsibilities
    ----------------
    - Estimate trade probability
    - Combine Decision confidence
    - Apply market regime adjustment
    - Apply AI dynamic weights

    Future versions
    ----------------
    - Bayesian Probability
    - Neural Networks
    - Reinforcement Learning
    """

    def __init__(
        self,
        optimizer: WeightOptimizer | None = None,
    ) -> None:

        self.optimizer = optimizer or WeightOptimizer()

    # --------------------------------------------------

    def estimate(
        self,
        data: ProbabilityInput,
    ) -> ProbabilityResult:

        probability = data.final_score

        # -----------------------------
        # Confidence effect
        # -----------------------------
        probability *= data.confidence

        # -----------------------------
        # Market regime adjustment
        # -----------------------------
        regime = data.regime.regime.value

        if regime == "bull":

            probability *= 1.10

        elif regime == "bear":

            probability *= 0.90

        elif regime == "high_volatility":

            probability *= 0.80

        elif regime == "low_volatility":

            probability *= 1.05

        elif regime == "breakout":

            probability *= 1.15

        # -----------------------------
        # AI Weight Quality
        # -----------------------------
        weights = self.optimizer.weights()

        average_weight = sum(
            weights.values()
        ) / len(weights)

        probability *= average_weight

        # -----------------------------
        # Clamp
        # -----------------------------
        probability = max(0.0, probability)

        probability = min(100.0, probability)

        return ProbabilityResult(
            probability=round(probability, 2),
            confidence=data.confidence,
            explanation=f"Probability estimated under {regime}",
        )