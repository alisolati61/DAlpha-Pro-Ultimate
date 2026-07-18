from __future__ import annotations

from typing import Dict

from src.ai.weight_optimizer import WeightOptimizer


class WeightManager:
    """
    Dynamic Weight Manager.

    Retrieves weights from the AI optimizer.

    Future versions:
    ----------------
    - Market Regime Profiles
    - Strategy Profiles
    - Session Profiles
    """

    _optimizer = WeightOptimizer()

    @classmethod
    def optimizer(cls) -> WeightOptimizer:
        return cls._optimizer

    @classmethod
    def weights(cls) -> Dict[str, float]:
        return cls._optimizer.weights()

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

        return round(total / total_weight, 2)

    @classmethod
    def update_module_performance(
        cls,
        module: str,
        performance: float,
    ) -> None:

        cls._optimizer.update_performance(
            module,
            performance,
        )

        cls._optimizer.optimize()