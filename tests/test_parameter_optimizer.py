"""Tests for deterministic numeric parameter grid search."""

from dataclasses import FrozenInstanceError
from math import inf, nan

import pytest

from src.backtesting.parameter_optimizer import (
    OptimizationResult,
    ParameterOptimizer,
)


def objective(
    parameters: dict[str, float],
) -> float:
    return -(
        abs(
            parameters["fast"]
            - 10.0
        )
        + abs(
            parameters["slow"]
            - 30.0
        )
    )


def valid_result() -> OptimizationResult:
    return OptimizationResult(
        best_parameters={
            "fast": 10.0,
            "slow": 30.0,
        },
        best_score=0.0,
        tested_combinations=9,
    )


def test_finds_best_combination_and_counts_grid() -> None:
    result = ParameterOptimizer().optimize(
        {
            "fast": [
                5,
                10,
                15,
            ],
            "slow": [
                20,
                30,
                40,
            ],
        },
        objective,
    )

    assert result == valid_result()
    assert result.parameter_count == 2


def test_empty_space_is_one_empty_combination() -> None:
    received: list[
        dict[str, float]
    ] = []

    result = ParameterOptimizer().optimize(
        {},
        lambda parameters: (
            received.append(
                parameters,
            )
            or 7
        ),
    )

    assert received == [
        {},
    ]

    assert result.best_parameters == {}
    assert result.best_score == 7.0
    assert result.tested_combinations == 1


def test_negative_scores_are_supported() -> None:
    result = ParameterOptimizer().optimize(
        {
            "x": [
                1,
                2,
                3,
            ],
        },
        lambda parameters: -parameters["x"],
    )

    assert result.best_parameters == {
        "x": 1.0,
    }

    assert result.best_score == -1.0


def test_first_combination_wins_score_ties() -> None:
    visited: list[
        dict[str, float]
    ] = []

    def tied(
        parameters: dict[str, float],
    ) -> float:
        visited.append(
            dict(parameters),
        )

        return 1.0

    result = ParameterOptimizer().optimize(
        {
            "a": [
                2,
                1,
            ],
            "b": [
                4,
                3,
            ],
        },
        tied,
    )

    assert visited == [
        {
            "a": 2.0,
            "b": 4.0,
        },
        {
            "a": 2.0,
            "b": 3.0,
        },
        {
            "a": 1.0,
            "b": 4.0,
        },
        {
            "a": 1.0,
            "b": 3.0,
        },
    ]

    assert result.best_parameters == {
        "a": 2.0,
        "b": 4.0,
    }


def test_duplicate_values_are_evaluated() -> None:
    calls = 0

    def count(
        parameters: dict[str, float],
    ) -> float:
        nonlocal calls

        calls += 1

        return parameters["x"]

    result = ParameterOptimizer().optimize(
        {
            "x": [
                1,
                1,
                2,
            ],
        },
        count,
    )

    assert calls == 3
    assert result.tested_combinations == 3


def test_generators_are_consumed_once() -> None:
    consumed: list[int] = []

    def values():
        for value in (
            1,
            2,
            3,
        ):
            consumed.append(
                value,
            )

            yield value

    result = ParameterOptimizer().optimize(
        {
            "x": values(),
        },
        lambda parameters: parameters["x"],
    )

    assert consumed == [
        1,
        2,
        3,
    ]

    assert result.best_parameters == {
        "x": 3.0,
    }


def test_inputs_and_scores_are_normalized_to_float() -> None:
    result = ParameterOptimizer().optimize(
        {
            "x": [
                1,
                2,
            ],
        },
        lambda parameters: 5,
    )

    assert result.best_parameters == {
        "x": 1.0,
    }

    assert isinstance(
        result.best_parameters["x"],
        float,
    )

    assert result.best_score == 5.0

    assert isinstance(
        result.best_score,
        float,
    )


def test_objective_mutation_cannot_corrupt_result() -> None:
    def mutate(
        parameters: dict[str, float],
    ) -> float:
        score = parameters["x"]

        parameters["x"] = 999.0
        parameters["extra"] = 1.0

        return score

    result = ParameterOptimizer().optimize(
        {
            "x": [
                1,
                2,
            ],
        },
        mutate,
    )

    assert result.best_parameters == {
        "x": 2.0,
    }


def test_source_space_is_not_mutated() -> None:
    space = {
        "x": [
            1,
            2,
        ],
    }

    ParameterOptimizer().optimize(
        space,
        lambda parameters: parameters["x"],
    )

    assert space == {
        "x": [
            1,
            2,
        ],
    }


def test_objective_exception_propagates() -> None:
    expected = RuntimeError(
        "failed",
    )

    def fail(
        parameters: dict[str, float],
    ) -> float:
        raise expected

    with pytest.raises(
        RuntimeError,
    ) as captured:
        ParameterOptimizer().optimize(
            {
                "x": [
                    1,
                ],
            },
            fail,
        )

    assert captured.value is expected


@pytest.mark.parametrize(
    "space",
    [
        None,
        1,
        [],
        (),
        "space",
        object(),
    ],
)
def test_rejects_non_dictionary_space(
    space: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "parameter_space must be "
            "a dictionary"
        ),
    ):
        ParameterOptimizer().optimize(
            space,  # type: ignore[arg-type]
            lambda parameters: 0.0,
        )


@pytest.mark.parametrize(
    "candidate",
    [
        None,
        1,
        "objective",
        object(),
    ],
)
def test_rejects_non_callable_objective(
    candidate: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="objective must be callable",
    ):
        ParameterOptimizer().optimize(
            {
                "x": [
                    1,
                ],
            },
            candidate,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    (
        "name",
        "error",
        "message",
    ),
    [
        (
            1,
            TypeError,
            "parameter names must be strings",
        ),
        (
            True,
            TypeError,
            "parameter names must be strings",
        ),
        (
            None,
            TypeError,
            "parameter names must be strings",
        ),
        (
            "",
            ValueError,
            "parameter names must not be empty",
        ),
        (
            "   ",
            ValueError,
            "parameter names must not be empty",
        ),
    ],
)
def test_validates_parameter_names(
    name: object,
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(
        error,
        match=message,
    ):
        ParameterOptimizer().optimize(
            {
                name: [  # type: ignore[dict-item]
                    1,
                ],
            },
            lambda parameters: 0.0,
        )


@pytest.mark.parametrize(
    "values",
    [
        None,
        1,
        1.5,
        object(),
        "1,2",
        b"1,2",
    ],
)
def test_rejects_invalid_value_iterable(
    values: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "values for parameter 'x' "
            "must be an iterable"
        ),
    ):
        ParameterOptimizer().optimize(
            {
                "x": values,  # type: ignore[dict-item]
            },
            lambda parameters: 0.0,
        )


def test_rejects_empty_value_iterable() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "parameter 'x' must contain "
            "at least one value"
        ),
    ):
        ParameterOptimizer().optimize(
            {
                "x": [],
            },
            lambda parameters: 0.0,
        )


@pytest.mark.parametrize(
    (
        "value",
        "error",
        "message",
    ),
    [
        (
            True,
            TypeError,
            "must be a real number",
        ),
        (
            "1",
            TypeError,
            "must be a real number",
        ),
        (
            None,
            TypeError,
            "must be a real number",
        ),
        (
            nan,
            ValueError,
            "must be finite",
        ),
        (
            inf,
            ValueError,
            "must be finite",
        ),
        (
            -inf,
            ValueError,
            "must be finite",
        ),
    ],
)
def test_validates_candidate_values(
    value: object,
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(
        error,
        match=message,
    ):
        ParameterOptimizer().optimize(
            {
                "x": [
                    1,
                    value,
                ],
            },  # type: ignore[list-item]
            lambda parameters: 0.0,
        )


@pytest.mark.parametrize(
    (
        "value",
        "error",
        "message",
    ),
    [
        (
            True,
            TypeError,
            "objective result must be a real number",
        ),
        (
            "1",
            TypeError,
            "objective result must be a real number",
        ),
        (
            None,
            TypeError,
            "objective result must be a real number",
        ),
        (
            nan,
            ValueError,
            "objective result must be finite",
        ),
        (
            inf,
            ValueError,
            "objective result must be finite",
        ),
        (
            -inf,
            ValueError,
            "objective result must be finite",
        ),
    ],
)
def test_validates_objective_result(
    value: object,
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(
        error,
        match=message,
    ):
        ParameterOptimizer().optimize(
            {
                "x": [
                    1,
                ],
            },
            lambda parameters: value,  # type: ignore[return-value]
        )


def test_result_copies_source_dictionary() -> None:
    parameters = {
        "x": 1.0,
    }

    result = OptimizationResult(
        best_parameters=parameters,
        best_score=1.0,
        tested_combinations=1,
    )

    parameters["x"] = 999.0

    assert result.best_parameters == {
        "x": 1.0,
    }


def test_result_is_frozen() -> None:
    result = valid_result()

    with pytest.raises(
        FrozenInstanceError,
    ):
        result.best_score = 1.0  # type: ignore[misc]


def test_result_rejects_non_dictionary_parameters() -> None:
    with pytest.raises(
        TypeError,
        match=(
            "best_parameters must be "
            "a dictionary"
        ),
    ):
        OptimizationResult(
            best_parameters=[],  # type: ignore[arg-type]
            best_score=0.0,
            tested_combinations=1,
        )


@pytest.mark.parametrize(
    (
        "parameters",
        "score",
        "count",
        "error",
        "message",
    ),
    [
        (
            {
                1: 1.0,
            },
            0.0,
            1,
            TypeError,
            "parameter names must be strings",
        ),
        (
            {
                "x": "1",
            },
            0.0,
            1,
            TypeError,
            "must be a real number",
        ),
        (
            {
                "x": nan,
            },
            0.0,
            1,
            ValueError,
            "must be finite",
        ),
        (
            {},
            "0",
            1,
            TypeError,
            "best_score must be a real number",
        ),
        (
            {},
            inf,
            1,
            ValueError,
            "best_score must be finite",
        ),
        (
            {},
            0.0,
            True,
            TypeError,
            "tested_combinations must be an integer",
        ),
        (
            {},
            0.0,
            0,
            ValueError,
            "tested_combinations must be greater than zero",
        ),
    ],
)
def test_result_validates_invariants(
    parameters: object,
    score: object,
    count: object,
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(
        error,
        match=message,
    ):
        OptimizationResult(
            best_parameters=parameters,  # type: ignore[arg-type]
            best_score=score,  # type: ignore[arg-type]
            tested_combinations=count,  # type: ignore[arg-type]
        )