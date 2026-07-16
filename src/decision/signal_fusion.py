from src.decision.models import DecisionInput
from src.decision.weight_manager import WeightManager


class SignalFusion:
    """
    Combines analysis scores into a unified signal.
    """

    @staticmethod
    def fuse(
        decision: DecisionInput,
    ) -> dict[str, float]:

        return {
            "technical": decision.technical_score,
            "smart_money": decision.smart_money_score,
            "orderflow": decision.orderflow_score,
            "sentiment": decision.sentiment_score,
            "onchain": decision.onchain_score,
        }

    @staticmethod
    def average(
        scores: dict[str, float],
    ) -> float:

        return WeightManager.weighted_average(scores)