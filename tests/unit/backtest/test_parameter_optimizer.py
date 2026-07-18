from src.backtesting.parameter_optimizer import (
    OptimizationResult,
    ParameterOptimizer,
)


def objective(params):

    fast = params["fast"]

    slow = params["slow"]

    return -(abs(fast - 10) + abs(slow - 30))


def test_optimizer_runs():

    optimizer = ParameterOptimizer()

    result = optimizer.optimize(

        {
            "fast": [5, 10, 15],
            "slow": [20, 30, 40],
        },

        objective,

    )

    assert isinstance(result, OptimizationResult)


def test_best_parameters():

    optimizer = ParameterOptimizer()

    result = optimizer.optimize(

        {
            "fast": [5, 10, 15],
            "slow": [20, 30, 40],
        },

        objective,

    )

    assert result.best_parameters["fast"] == 10

    assert result.best_parameters["slow"] == 30


def test_best_score():

    optimizer = ParameterOptimizer()

    result = optimizer.optimize(

        {
            "fast": [5, 10],
            "slow": [20, 30],
        },

        objective,

    )

    assert result.best_score == 0.0


def test_combination_count():

    optimizer = ParameterOptimizer()

    result = optimizer.optimize(

        {
            "a": [1, 2],
            "b": [1, 2, 3],
        },

        lambda p: 1,

    )

    assert result.tested_combinations == 6


def test_result_types():

    optimizer = ParameterOptimizer()

    result = optimizer.optimize(

        {
            "x": [1],
        },

        lambda p: 1,

    )

    assert isinstance(result.best_parameters, dict)

    assert isinstance(result.best_score, float)

    assert isinstance(result.tested_combinations, int)