from src.ai.weight_optimizer import (
    ModuleWeight,
    WeightOptimizer,
)


def test_default_weights():

    optimizer = WeightOptimizer()

    weights = optimizer.weights()

    assert isinstance(weights, dict)

    assert weights["technical"] == 0.25
    assert weights["smart_money"] == 0.30
    assert weights["orderflow"] == 0.20
    assert weights["sentiment"] == 0.10
    assert weights["onchain"] == 0.15


def test_update_performance():

    optimizer = WeightOptimizer()

    optimizer.update_performance(
        "technical",
        0.90,
    )

    summary = optimizer.summary()

    assert summary["technical"]["performance"] == 0.90


def test_optimize_changes_weights():

    optimizer = WeightOptimizer()

    optimizer.update_performance(
        "technical",
        0.90,
    )

    optimizer.update_performance(
        "smart_money",
        0.50,
    )

    optimizer.update_performance(
        "orderflow",
        0.20,
    )

    optimizer.update_performance(
        "sentiment",
        0.10,
    )

    optimizer.update_performance(
        "onchain",
        0.05,
    )

    optimizer.optimize()

    weights = optimizer.weights()

    total = round(sum(weights.values()), 4)

    assert total == 1.0

    assert (
        weights["technical"]
        >
        weights["smart_money"]
        >
        weights["orderflow"]
    )


def test_reset():

    optimizer = WeightOptimizer()

    optimizer.update_performance(
        "technical",
        0.95,
    )

    optimizer.optimize()

    optimizer.reset()

    weights = optimizer.weights()

    assert weights["technical"] == 0.25
    assert weights["smart_money"] == 0.30
    assert weights["orderflow"] == 0.20
    assert weights["sentiment"] == 0.10
    assert weights["onchain"] == 0.15


def test_summary():

    optimizer = WeightOptimizer()

    optimizer.update_performance(
        "technical",
        0.75,
    )

    summary = optimizer.summary()

    assert "technical" in summary

    assert "weight" in summary["technical"]

    assert "performance" in summary["technical"]


def test_unknown_module():

    optimizer = WeightOptimizer()

    optimizer.update_performance(
        "UNKNOWN",
        1.0,
    )

    weights = optimizer.weights()

    assert "UNKNOWN" not in weights


def test_module_weight_dataclass():

    module = ModuleWeight(
        name="technical",
        weight=0.25,
        performance=0.80,
    )

    assert module.name == "technical"

    assert module.weight == 0.25

    assert module.performance == 0.80