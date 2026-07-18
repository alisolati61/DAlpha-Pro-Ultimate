from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(slots=True)
class ModuleWeight:
    """
    Represents a single module weight.
    """

    name: str
    weight: float
    performance: float = 0.0


class WeightOptimizer:
    """
    AI Weight Optimizer.

    Responsibilities
    ----------------
    - Store module weights
    - Update performance
    - Optimize weights
    - Normalize weights

    Future versions
    ---------------
    - Bayesian Optimization
    - Reinforcement Learning
    - Genetic Algorithms
    """

    DEFAULT_WEIGHTS: Dict[str, float] = {
        "technical": 0.25,
        "smart_money": 0.30,
        "orderflow": 0.20,
        "sentiment": 0.10,
        "onchain": 0.15,
    }

    def __init__(self) -> None:

        self._weights = {
            name: ModuleWeight(
                name=name,
                weight=value,
            )
            for name, value in self.DEFAULT_WEIGHTS.items()
        }

    # --------------------------------------------------

    def weights(self) -> Dict[str, float]:

        return {
            name: module.weight
            for name, module in self._weights.items()
        }

    # --------------------------------------------------

    def update_performance(
        self,
        module: str,
        performance: float,
    ) -> None:

        if module not in self._weights:
            return

        self._weights[module].performance = performance

    # --------------------------------------------------

    def optimize(self) -> None:

        total = sum(
            max(module.performance, 0.01)
            for module in self._weights.values()
        )

        if total == 0:
            return

        for module in self._weights.values():

            module.weight = round(
                max(module.performance, 0.01) / total,
                4,
            )

    # --------------------------------------------------

    def reset(self) -> None:

        for name, value in self.DEFAULT_WEIGHTS.items():

            self._weights[name].weight = value

            self._weights[name].performance = 0.0

    # --------------------------------------------------

    def summary(self) -> Dict[str, Dict[str, float]]:

        return {
            name: {
                "weight": module.weight,
                "performance": module.performance,
            }
            for name, module in self._weights.items()
        }