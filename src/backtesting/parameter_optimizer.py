"""Deterministic grid-search optimization for numeric parameters.

The optimizer evaluates the Cartesian product of the supplied parameter
values in dictionary insertion order. The highest finite objective score wins.
When multiple combinations have the same score, the first combination is
retained so repeated runs remain deterministic.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import product
from math import isfinite
from numbers import Real


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    """Immutable summary of a completed parameter grid search."""

    best_parameters: dict[str, float]
    best_score: float
    tested_combinations: int

    def __post_init__(self) -> None:
        if not isinstance(self.best_parameters, dict):
            raise TypeError(
                "best_parameters must be a dictionary"
            )

        normalized_parameters: dict[str, float] = {}

        for name, value in self.best_parameters.items():
            normalized_name = _validate_parameter_name(
                name,
            )

            normalized_parameters[
                normalized_name
            ] = _validate_number(
                f"best_parameters[{normalized_name!r}]",
                value,
            )

        best_score = _validate_number(
            "best_score",
            self.best_score,
        )

        tested_combinations = _validate_positive_integer(
            "tested_combinations",
            self.tested_combinations,
        )

        object.__setattr__(
            self,
            "best_parameters",
            normalized_parameters,
        )

        object.__setattr__(
            self,
            "best_score",
            best_score,
        )

        object.__setattr__(
            self,
            "tested_combinations",
            tested_combinations,
        )

    @property
    def parameter_count(self) -> int:
        """Return the number of parameters in the winning combination."""

        return len(
            self.best_parameters,
        )


class ParameterOptimizer:
    """Exhaustively maximize a finite numeric parameter grid."""

    def optimize(
        self,
        parameter_space: dict[str, Iterable[float]],
        objective: Callable[[dict[str, float]], float],
    ) -> OptimizationResult:
        """Evaluate every combination and return the highest-scoring one.

        Parameter values and objective scores must be finite real numbers.
        Value iterables are materialized exactly once, allowing generators.

        An empty parameter dictionary represents one valid empty combination.

        A parameter with no candidate values is rejected because no objective
        evaluation could produce a meaningful result.
        """

        if not callable(objective):
            raise TypeError(
                "objective must be callable"
            )

        normalized_space = _normalize_parameter_space(
            parameter_space,
        )

        names = tuple(
            name
            for name, _ in normalized_space
        )

        value_sets = tuple(
            values
            for _, values in normalized_space
        )

        best_parameters: dict[str, float] | None = None
        best_score: float | None = None
        tested_combinations = 0

        for combination in product(
            *value_sets,
        ):
            parameters = dict(
                zip(
                    names,
                    combination,
                    strict=True,
                )
            )

            score = _validate_number(
                "objective result",
                objective(
                    dict(parameters),
                ),
            )

            tested_combinations += 1

            if (
                best_score is None
                or score > best_score
            ):
                best_score = score
                best_parameters = parameters

        if (
            best_score is None
            or best_parameters is None
        ):
            raise RuntimeError(
                "parameter optimization produced no combinations"
            )

        return OptimizationResult(
            best_parameters=best_parameters,
            best_score=best_score,
            tested_combinations=tested_combinations,
        )


def _normalize_parameter_space(
    parameter_space: object,
) -> tuple[
    tuple[
        str,
        tuple[float, ...],
    ],
    ...,
]:
    if not isinstance(
        parameter_space,
        dict,
    ):
        raise TypeError(
            "parameter_space must be a dictionary"
        )

    normalized: list[
        tuple[
            str,
            tuple[float, ...],
        ]
    ] = []

    for raw_name, raw_values in parameter_space.items():
        name = _validate_parameter_name(
            raw_name,
        )

        if isinstance(
            raw_values,
            (
                str,
                bytes,
                bytearray,
            ),
        ):
            raise TypeError(
                f"values for parameter {name!r} must be an iterable "
                "of real numbers"
            )

        try:
            iterator = iter(
                raw_values,
            )
        except TypeError as exc:
            raise TypeError(
                f"values for parameter {name!r} must be an iterable "
                "of real numbers"
            ) from exc

        values = tuple(
            _validate_number(
                f"parameter {name!r} value at index {index}",
                value,
            )
            for index, value in enumerate(
                iterator,
            )
        )

        if not values:
            raise ValueError(
                f"parameter {name!r} must contain at least one value"
            )

        normalized.append(
            (
                name,
                values,
            )
        )

    return tuple(
        normalized,
    )


def _validate_parameter_name(
    value: object,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            "parameter names must be strings"
        )

    if not value.strip():
        raise ValueError(
            "parameter names must not be empty"
        )

    return value


def _validate_number(
    name: str,
    value: object,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
    ):
        raise TypeError(
            f"{name} must be a real number"
        )

    number = float(
        value,
    )

    if not isfinite(number):
        raise ValueError(
            f"{name} must be finite"
        )

    return number


def _validate_positive_integer(
    name: str,
    value: object,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
    ):
        raise TypeError(
            f"{name} must be an integer"
        )

    if value <= 0:
        raise ValueError(
            f"{name} must be greater than zero"
        )

    return value


__all__ = [
    "OptimizationResult",
    "ParameterOptimizer",
]