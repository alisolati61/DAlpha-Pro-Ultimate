from dataclasses import dataclass


@dataclass
class ScoreResult:
    total_score: float
    decision: str


class ScoringEngine:

    def evaluate(self, scores: dict) -> ScoreResult:

        total = sum(scores.values())

        total = max(0, min(100, total))

        if total >= 85:
            decision = "STRONG_BUY"

        elif total >= 70:
            decision = "BUY"

        elif total >= 55:
            decision = "NEUTRAL"

        elif total >= 40:
            decision = "SELL"

        else:
            decision = "STRONG_SELL"

        return ScoreResult(
            total_score=round(total, 2),
            decision=decision,
        )