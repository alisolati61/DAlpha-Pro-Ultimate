"""Public API for validated backtesting engines and result models."""

from __future__ import annotations

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


__all__ = (
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