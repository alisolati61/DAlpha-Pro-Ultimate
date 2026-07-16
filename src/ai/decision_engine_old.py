from dataclasses import dataclass


@dataclass
class Decision:

    action: str
    confidence: float
    reason: str


class DecisionEngine:

    def decide(
        self,
        score: float,
        signal_valid: bool,
    ) -> Decision:

        if not signal_valid:

            return Decision(
                action="NO TRADE",
                confidence=0,
                reason="Signal validation failed",
            )

        if score >= 85:

            return Decision(
                action="BUY",
                confidence=score,
                reason="High confidence",
            )

        if score <= 20:

            return Decision(
                action="SELL",
                confidence=100-score,
                reason="High bearish confidence",
            )

        return Decision(
            action="WAIT",
            confidence=score,
            reason="No clear edge",
        )