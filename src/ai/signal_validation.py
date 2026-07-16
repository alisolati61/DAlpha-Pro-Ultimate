from dataclasses import dataclass


@dataclass
class ValidationResult:
    valid: bool
    confidence: float
    reason: str


class SignalValidationEngine:

    def validate(self, scores: dict) -> ValidationResult:

        failed = []

        required = {
            "trend": 10,
            "smc": 10,
            "orderflow": 10,
            "risk": 5,
        }

        for key, minimum in required.items():

            if scores.get(key, 0) < minimum:
                failed.append(key)

        if failed:

            return ValidationResult(
                valid=False,
                confidence=0,
                reason="Missing confirmation: " + ", ".join(failed),
            )

        confidence = sum(scores.values())

        confidence = min(confidence, 100)

        return ValidationResult(
            valid=True,
            confidence=confidence,
            reason="Signal validated",
        )