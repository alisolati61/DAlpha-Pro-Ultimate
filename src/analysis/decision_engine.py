from __future__ import annotations

from src.analysis.signal_engine import Signal


class DecisionEngine:
    """
    Final trading decision engine.
    """

    def decide(
        self,
        signal: Signal,
        minimum_confidence: float = 70,
    ) -> Signal:

        if signal.direction == "NEUTRAL":
            return signal

        if signal.confidence < minimum_confidence:

            return Signal(
                direction="NEUTRAL",
                confidence=signal.confidence,
                reason="Confidence Too Low",
            )

        return signal