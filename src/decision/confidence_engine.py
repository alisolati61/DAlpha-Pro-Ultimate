class ConfidenceEngine:
    """
    Calculates confidence for a trading decision.

    This class is intentionally isolated so that
    future versions can include:

    - AI confidence
    - Historical accuracy
    - Signal agreement
    - Market regime
    """

    @staticmethod
    def calculate(final_score: float) -> float:

        confidence = final_score / 100

        confidence = max(0.0, confidence)
        confidence = min(1.0, confidence)

        return round(confidence, 2)