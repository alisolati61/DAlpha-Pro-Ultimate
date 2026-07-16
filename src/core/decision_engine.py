from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class DecisionResult:
    action: str
    score: float
    confidence: float
    reason: str


class DecisionEngine:

    def __init__(self):
        self.minimum_score = 85

    def evaluate(self, scores: Dict[str, float]) -> DecisionResult:

        total_score = sum(scores.values())

        confidence = min(total_score / 100, 1.0)

        if total_score >= self.minimum_score:
            action = "BUY"
        else:
            action = "HOLD"

        return DecisionResult(
            action=action,
            score=total_score,
            confidence=confidence,
            reason="Scoring Engine Decision"
        )