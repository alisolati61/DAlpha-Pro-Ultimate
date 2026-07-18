from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(slots=True)
class ValidationResult:
    """
    Result returned by AI Signal Validation Engine.
    """

    valid: bool
    confidence: float
    score: float
    passed_checks: int
    failed_checks: list[str] = field(default_factory=list)
    reason: str = ""


class SignalValidationEngine:
    """
    AI Signal Validation Engine.

    Responsibilities
    ----------------
    • Validate confluence between all engines
    • Calculate weighted confidence
    • Reject weak signals
    • Prepare output for Decision Engine

    Future versions:
    ----------------
    - Historical accuracy weighting
    - Machine Learning confidence
    - Adaptive thresholds
    - Market regime awareness
    """

    DEFAULT_THRESHOLDS: Dict[str, float] = {
        "trend": 10.0,
        "smc": 10.0,
        "orderflow": 10.0,
        "risk": 5.0,
    }

    DEFAULT_WEIGHTS: Dict[str, float] = {
        "trend": 0.30,
        "smc": 0.30,
        "orderflow": 0.25,
        "risk": 0.15,
    }

    def validate(
        self,
        scores: Dict[str, float],
    ) -> ValidationResult:

        failed: list[str] = []
        passed = 0

        # -----------------------------
        # Minimum Threshold Validation
        # -----------------------------
        for name, minimum in self.DEFAULT_THRESHOLDS.items():

            value = scores.get(name, 0.0)

            if value >= minimum:
                passed += 1
            else:
                failed.append(name)

        # -----------------------------
        # Weighted Score
        # -----------------------------
        weighted_score = 0.0
        total_weight = 0.0

        for name, weight in self.DEFAULT_WEIGHTS.items():

            value = scores.get(name, 0.0)

            weighted_score += value * weight
            total_weight += weight

        if total_weight > 0:
            weighted_score /= total_weight

        weighted_score = round(weighted_score, 2)

        # -----------------------------
        # Confidence
        # -----------------------------
        confidence = round(
            min(100.0, weighted_score),
            2,
        )

        # -----------------------------
        # Decision
        # -----------------------------
        if failed:

            return ValidationResult(
                valid=False,
                confidence=confidence,
                score=weighted_score,
                passed_checks=passed,
                failed_checks=failed,
                reason="Missing confirmation: " + ", ".join(failed),
            )

        return ValidationResult(
            valid=True,
            confidence=confidence,
            score=weighted_score,
            passed_checks=passed,
            failed_checks=[],
            reason="Signal validated",
        )