from __future__ import annotations

from src.ai.feedback_loop import FeedbackLoop
from src.ai.performance_tracker import PerformanceTracker
from src.ai.weight_optimizer import WeightOptimizer


class ConfidenceEngine:
    """
    Adaptive Confidence Engine.

    Calculates trading confidence using:

    - Decision Score
    - Historical Win Rate
    - Average Confidence
    - Dynamic AI Weights

    Future:
    --------
    - Market Regime
    - Symbol Statistics
    - Session Statistics
    - AI Probability Model
    """

    def __init__(
        self,
        tracker: PerformanceTracker | None = None,
        feedback: FeedbackLoop | None = None,
        optimizer: WeightOptimizer | None = None,
    ) -> None:

        self.tracker = tracker or PerformanceTracker()

        self.feedback = feedback or FeedbackLoop()

        self.optimizer = optimizer or WeightOptimizer()

    # --------------------------------------------------

    def calculate(
        self,
        final_score: float,
    ) -> float:

        # -----------------------------
        # Base confidence
        # -----------------------------
        confidence = final_score

        # -----------------------------
        # Historical Win Rate
        # -----------------------------
        if self.tracker.trades > 0:

            confidence *= (
                self.tracker.win_rate / 100
            )

        # -----------------------------
        # Feedback Success
        # -----------------------------
        if self.feedback.total_events > 0:

            confidence *= (
                self.feedback.success_rate / 100
            )

        # -----------------------------
        # AI Weight Quality
        # -----------------------------
        weights = self.optimizer.weights()

        weight_bonus = sum(
            weights.values()
        ) / len(weights)

        confidence *= weight_bonus

        # -----------------------------
        # Clamp
        # -----------------------------
        confidence = max(0.0, confidence)

        confidence = min(confidence, 100.0)

        return round(confidence / 100, 2)