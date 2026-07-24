"""Tests for the public backtesting package API."""

from __future__ import annotations

import src.backtesting as backtesting
from src.backtesting.backtest_engine import (
    BacktestEngine,
    BacktestResult,
)
from src.backtesting.monte_carlo import (
    MonteCarloEngine,
    MonteCarloResult,
)
from src.backtesting.parameter_optimizer import (
    OptimizationResult,
    ParameterOptimizer,
)
from src.backtesting.report_generator import (
    BacktestReport,
    Clock,
    ReportGenerator,
)
from src.backtesting.statistics_engine import (
    BacktestStatistics,
    StatisticsEngine,
)
from src.backtesting.strategy_runner import (
    CandleSignal,
    StrategyRunner,
)
from src.backtesting.trade_simulator import (
    TradeRequest,
    TradeSimulationResult,
    TradeSimulator,
)
from src.backtesting.walk_forward import (
    WalkForward,
    WalkForwardWindow,
)


EXPECTED_EXPORTS = (
    "BacktestEngine",
    "BacktestReport",
    "BacktestResult",
    "BacktestStatistics",
    "CandleSignal",
    "Clock",
    "MonteCarloEngine",
    "MonteCarloResult",
    "OptimizationResult",
    "ParameterOptimizer",
    "ReportGenerator",
    "StatisticsEngine",
    "StrategyRunner",
    "TradeRequest",
    "TradeSimulationResult",
    "TradeSimulator",
    "WalkForward",
    "WalkForwardWindow",
)


def test_public_exports_are_explicit_and_stable() -> None:
    assert backtesting.__all__ == EXPECTED_EXPORTS


def test_public_exports_have_no_duplicates() -> None:
    assert len(backtesting.__all__) == len(
        set(backtesting.__all__)
    )


def test_every_public_export_exists() -> None:
    for export_name in backtesting.__all__:
        assert hasattr(
            backtesting,
            export_name,
        ), f"missing backtesting export: {export_name}"


def test_engine_exports_reference_original_classes() -> None:
    assert backtesting.BacktestEngine is BacktestEngine
    assert backtesting.MonteCarloEngine is MonteCarloEngine
    assert backtesting.ParameterOptimizer is ParameterOptimizer
    assert backtesting.ReportGenerator is ReportGenerator
    assert backtesting.StatisticsEngine is StatisticsEngine
    assert backtesting.StrategyRunner is StrategyRunner
    assert backtesting.TradeSimulator is TradeSimulator
    assert backtesting.WalkForward is WalkForward


def test_model_and_alias_exports_reference_original_objects() -> None:
    assert backtesting.BacktestReport is BacktestReport
    assert backtesting.BacktestResult is BacktestResult
    assert backtesting.BacktestStatistics is BacktestStatistics
    assert backtesting.CandleSignal is CandleSignal
    assert backtesting.Clock is Clock
    assert backtesting.MonteCarloResult is MonteCarloResult
    assert backtesting.OptimizationResult is OptimizationResult
    assert backtesting.TradeRequest is TradeRequest

    assert (
        backtesting.TradeSimulationResult
        is TradeSimulationResult
    )

    assert backtesting.WalkForwardWindow is WalkForwardWindow


def test_wildcard_import_contains_only_public_exports() -> None:
    namespace: dict[str, object] = {}

    exec(
        "from src.backtesting import *",
        namespace,
    )

    imported_names = {
        name
        for name in namespace
        if not name.startswith("__")
    }

    assert imported_names == set(EXPECTED_EXPORTS)


def test_exported_engines_can_be_constructed() -> None:
    assert isinstance(
        backtesting.BacktestEngine(),
        BacktestEngine,
    )

    assert isinstance(
        backtesting.MonteCarloEngine(),
        MonteCarloEngine,
    )

    assert isinstance(
        backtesting.ParameterOptimizer(),
        ParameterOptimizer,
    )

    assert isinstance(
        backtesting.ReportGenerator(),
        ReportGenerator,
    )

    assert isinstance(
        backtesting.StatisticsEngine(),
        StatisticsEngine,
    )

    assert isinstance(
        backtesting.StrategyRunner(),
        StrategyRunner,
    )

    assert isinstance(
        backtesting.TradeSimulator(),
        TradeSimulator,
    )

    assert isinstance(
        backtesting.WalkForward(),
        WalkForward,
    )