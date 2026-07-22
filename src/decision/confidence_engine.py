from __future__ import annotations

from src.ai.feedback_loop import FeedbackLoop
from src.ai.performance_tracker import PerformanceTracker
from src.ai.weight_optimizer import WeightOptimizer


class ConfidenceEngine:
    """
    Adaptive Confidence Engine.

    Supports two modes:

    1. Static calculation:
        ConfidenceEngine.calculate(80) -> 0.80

    2. Adaptive calculation:
        engine = ConfidenceEngine(...)
        engine.calculate_adaptive(80)
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
    # Simple API (used by tests)
    # --------------------------------------------------

    @staticmethod
    def calculate(
        final_score: float,
    ) -> float:
        """
        Convert a score in the range 0..100 to confidence 0.0..1.0.

        Values outside the range are clamped.
        """

        score = max(0.0, min(float(final_score), 100.0))

        return round(score / 100, 2)

    # --------------------------------------------------
    # Adaptive AI API
    # --------------------------------------------------

    def calculate_adaptive(
        self,
        final_score: float,
    ) -> float:

        confidence = float(final_score)

        if self.tracker.trades > 0:
            confidence *= (
                self.tracker.win_rate / 100
            )

        if self.feedback.total_events > 0:
            confidence *= (
                self.feedback.success_rate / 100
            )

        weights = self.optimizer.weights()

        if weights:
            weight_bonus = (
                sum(weights.values()) / len(weights)
            )
            confidence *= weight_bonus

        confidence = max(
            0.0,
            min(confidence, 100.0),
        )

        return round(confidence / 100, 2)