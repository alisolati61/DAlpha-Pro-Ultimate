from __future__ import annotations

from src.ai.feedback_loop import FeedbackLoop
from src.ai.performance_tracker import PerformanceTracker
from src.ai.weight_optimizer import WeightOptimizer

from src.decision.models import (
    DecisionInput,
    DecisionResult,
)

from src.decision.signal_fusion import SignalFusion
from src.decision.confidence_engine import ConfidenceEngine
from src.decision.trade_validator import TradeValidator


class DecisionEngine:
    """
    Central Decision Engine.

    Responsibilities:

    - Collect analysis scores
    - Fuse signals
    - Calculate final score
    - Calculate adaptive confidence
    - Validate trade
    - Produce final trading decision

    Future versions:

    - AI Decision Layer
    - Probability Engine
    - Market Regime Filter
    - Multi-Timeframe Confirmation
    - Strategy Profiles
    """

    def __init__(
        self,
        minimum_score: float = 70.0,
    ) -> None:

        self.minimum_score = minimum_score

        self.performance_tracker = PerformanceTracker()

        self.feedback_loop = FeedbackLoop()

        self.weight_optimizer = WeightOptimizer()

        self.confidence_engine = ConfidenceEngine(
            tracker=self.performance_tracker,
            feedback=self.feedback_loop,
            optimizer=self.weight_optimizer,
        )

    # --------------------------------------------------

    def evaluate(
        self,
        decision: DecisionInput,
    ) -> DecisionResult:

        # -----------------------------
        # Signal Fusion
        # -----------------------------
        scores = SignalFusion.fuse(decision)

        final_score = SignalFusion.average(scores)

        # -----------------------------
        # Adaptive Confidence
        # -----------------------------
        confidence = self.confidence_engine.calculate(
            final_score
        )

        # -----------------------------
        # Trade Validation
        # -----------------------------
        approved, reason = TradeValidator.validate(
            decision
        )

        if not approved:

            return DecisionResult(
                action="HOLD",
                confidence=confidence,
                final_score=round(final_score, 2),
                scores=scores,
                reason=reason,
            )

        # -----------------------------
        # Final Decision
        # -----------------------------
        action = (
            "BUY"
            if final_score >= self.minimum_score
            else "HOLD"
        )

        return DecisionResult(
            action=action,
            confidence=confidence,
            final_score=round(final_score, 2),
            scores=scores,
            reason="Decision Engine evaluation",
        )