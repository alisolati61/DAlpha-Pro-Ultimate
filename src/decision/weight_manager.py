from typing import Dict


class WeightManager:
    """
    Provides weights for every analysis module.

    Future versions may load weights from:

    - AI optimizer
    - Configuration
    - Strategy profile
    - Market regime
    """

    DEFAULT_WEIGHTS = {
        "technical": 0.25,
        "smart_money": 0.30,
        "orderflow": 0.20,
        "sentiment": 0.10,
        "onchain": 0.15,
    }

    @classmethod
    def weights(cls) -> Dict[str, float]:
        return cls.DEFAULT_WEIGHTS.copy()

    @classmethod
    def weighted_average(
        cls,
        scores: Dict[str, float],
    ) -> float:

        weights = cls.weights()

        total = 0.0
        total_weight = 0.0

        for key, score in scores.items():

            weight = weights.get(key, 0.0)

            total += score * weight

            total_weight += weight

        if total_weight == 0:
            return 0.0

        return total / total_weight