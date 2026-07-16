from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ConfidenceResult:
    confidence: float
    signal_count: int
    passed: bool


class ConfidenceAggregator:
    """
    Aggregates weighted scores into one confidence value.
    """

    def aggregate(
        self,
        scores: list[float],
        threshold: float = 70.0,
    ) -> ConfidenceResult:

        if not scores:

            return ConfidenceResult(
                confidence=0.0,
                signal_count=0,
                passed=False,
            )

        confidence = sum(scores) / len(scores)

        return ConfidenceResult(
            confidence=round(confidence, 2),
            signal_count=len(scores),
            passed=confidence >= threshold,
        )