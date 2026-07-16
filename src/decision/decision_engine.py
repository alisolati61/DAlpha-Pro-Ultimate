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

    Responsibilities

    - Fuse all analysis scores
    - Produce weighted score
    - Calculate confidence
    - Validate trade
    - Produce BUY / SELL / HOLD

    Future:

    - AI Decision Layer
    - Dynamic Market Regime
    - Adaptive Thresholds
    - Strategy Profiles
    """

    BUY_THRESHOLD = 70.0
    SELL_THRESHOLD = 30.0
    MIN_CONFIDENCE = 0.70

    def __init__(
        self,
        minimum_score: float = BUY_THRESHOLD,
    ):
        self.minimum_score = minimum_score

    def evaluate(
        self,
        decision: DecisionInput,
    ) -> DecisionResult:

        # ---------------------------------
        # Signal Fusion
        # ---------------------------------

        scores = SignalFusion.fuse(
            decision
        )

        final_score = SignalFusion.average(
            scores
        )

        # ---------------------------------
        # Confidence
        # ---------------------------------

        confidence = ConfidenceEngine.calculate(
            final_score
        )

        # ---------------------------------
        # Trade Validation
        # ---------------------------------

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

        # ---------------------------------
        # Final Decision
        # ---------------------------------

        if (
            final_score >= self.BUY_THRESHOLD
            and confidence >= self.MIN_CONFIDENCE
        ):

            action = "BUY"

            reason = "BUY threshold satisfied"

        elif (
            final_score <= self.SELL_THRESHOLD
            and confidence >= self.MIN_CONFIDENCE
        ):

            action = "SELL"

            reason = "SELL threshold satisfied"

        else:

            action = "HOLD"

            reason = "Conditions not satisfied"

        return DecisionResult(
            action=action,
            confidence=confidence,
            final_score=round(final_score, 2),
            scores=scores,
            reason=reason,
        )