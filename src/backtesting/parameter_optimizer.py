from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Callable, Iterable


@dataclass(slots=True)
class OptimizationResult:
    """
    Best parameter set discovered.
    """

    best_parameters: dict[str, float]
    best_score: float
    tested_combinations: int


class ParameterOptimizer:
    """
    Simple Grid Search Optimizer.

    Future
    -------
    - Bayesian Optimization
    - Genetic Algorithm
    - Particle Swarm
    - HyperOpt
    """

    def optimize(
        self,
        parameter_space: dict[str, Iterable[float]],
        objective: Callable[[dict[str, float]], float],
    ) -> OptimizationResult:

        names = list(parameter_space.keys())

        values = [
            list(parameter_space[name])
            for name in names
        ]

        best_score = float("-inf")

        best_parameters: dict[str, float] = {}

        tested = 0

        for combination in product(*values):

            params = dict(
                zip(
                    names,
                    combination,
                )
            )

            score = float(
                objective(params)
            )

            tested += 1

            if score > best_score:

                best_score = score

                best_parameters = params

        return OptimizationResult(
            best_parameters=best_parameters,
            best_score=float(best_score),
            tested_combinations=tested,
        )