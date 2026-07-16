from src.decision.models import DecisionInput


class TradeValidator:
    """
    Validates whether a trade is allowed.

    Future versions will validate:

    - Risk Manager
    - Daily Loss
    - Max Drawdown
    - Session Filter
    - Spread Filter
    - News Filter
    - Circuit Breaker
    """

    MINIMUM_RISK_SCORE = 50.0

    @classmethod
    def validate(
        cls,
        decision: DecisionInput,
    ) -> tuple[bool, str]:

        if decision.risk_score < cls.MINIMUM_RISK_SCORE:
            return (
                False,
                "Risk manager rejected trade",
            )

        return (
            True,
            "Trade approved",
        )