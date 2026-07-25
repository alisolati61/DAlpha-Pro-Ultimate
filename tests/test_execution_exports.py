"""Tests for the stable public execution API."""

import importlib

import src.execution as execution
from src.execution.balance_tracker import (
    AssetBalance as ModuleAssetBalance,
)
from src.execution.balance_tracker import (
    BalanceTracker as ModuleBalanceTracker,
)
from src.execution.execution_engine import (
    ExecutionEngine as ModuleExecutionEngine,
)
from src.execution.execution_engine import (
    ExecutionRequest as ModuleExecutionRequest,
)
from src.execution.execution_history import (
    ExecutionHistory as ModuleExecutionHistory,
)
from src.execution.execution_manager import (
    ExecutionManager as ModuleExecutionManager,
)
from src.execution.execution_manager import (
    ExecutionResult as ModuleExecutionResult,
)
from src.execution.execution_report import (
    ExecutionReport as ModuleExecutionReport,
)
from src.execution.execution_report import (
    ExecutionReportFactory as ModuleExecutionReportFactory,
)
from src.execution.order_manager import (
    OrderManager as ModuleOrderManager,
)
from src.execution.order_tracker import (
    OrderState as ModuleOrderState,
)
from src.execution.order_tracker import (
    OrderStatus as ModuleOrderStatus,
)
from src.execution.order_tracker import (
    OrderTracker as ModuleOrderTracker,
)
from src.execution.paper_trading import (
    PaperTrade as ModulePaperTrade,
)
from src.execution.paper_trading import (
    PaperTradeSide as ModulePaperTradeSide,
)
from src.execution.paper_trading import (
    PaperTradingEngine as ModulePaperTradingEngine,
)
from src.execution.portfolio_manager import (
    PortfolioManager as ModulePortfolioManager,
)
from src.execution.portfolio_sync import (
    PortfolioState as ModulePortfolioState,
)
from src.execution.portfolio_sync import (
    PortfolioSynchronizer as ModulePortfolioSynchronizer,
)
from src.execution.position_manager import (
    Position as ModulePosition,
)
from src.execution.position_manager import (
    PositionManager as ModulePositionManager,
)
from src.execution.slippage import (
    OrderSide as ModuleOrderSide,
)
from src.execution.slippage import (
    SlippageCalculator as ModuleSlippageCalculator,
)
from src.execution.slippage import (
    SlippageResult as ModuleSlippageResult,
)
from src.execution.smart_router import (
    ExecutionRoute as ModuleExecutionRoute,
)
from src.execution.smart_router import (
    RouteCandidate as ModuleRouteCandidate,
)
from src.execution.smart_router import (
    RoutingDecision as ModuleRoutingDecision,
)
from src.execution.smart_router import (
    SmartRouter as ModuleSmartRouter,
)


EXPECTED_EXPORTS = (
    "AssetBalance",
    "BalanceTracker",
    "ExecutionEngine",
    "ExecutionHistory",
    "ExecutionManager",
    "ExecutionReport",
    "ExecutionReportFactory",
    "ExecutionRequest",
    "ExecutionResult",
    "ExecutionRoute",
    "OrderManager",
    "OrderSide",
    "OrderState",
    "OrderStatus",
    "OrderTracker",
    "PaperTrade",
    "PaperTradeSide",
    "PaperTradingEngine",
    "PortfolioManager",
    "PortfolioState",
    "PortfolioSynchronizer",
    "Position",
    "PositionManager",
    "RouteCandidate",
    "RoutingDecision",
    "SlippageCalculator",
    "SlippageResult",
    "SmartRouter",
)


def test_public_all_is_exact_and_deterministic() -> None:
    assert execution.__all__ == EXPECTED_EXPORTS
    assert len(execution.__all__) == len(
        set(execution.__all__)
    )


def test_every_declared_export_exists() -> None:
    for name in EXPECTED_EXPORTS:
        assert hasattr(execution, name)


def test_package_exports_are_original_objects() -> None:
    expected = {
        "AssetBalance": ModuleAssetBalance,
        "BalanceTracker": ModuleBalanceTracker,
        "ExecutionEngine": ModuleExecutionEngine,
        "ExecutionHistory": ModuleExecutionHistory,
        "ExecutionManager": ModuleExecutionManager,
        "ExecutionReport": ModuleExecutionReport,
        "ExecutionReportFactory": ModuleExecutionReportFactory,
        "ExecutionRequest": ModuleExecutionRequest,
        "ExecutionResult": ModuleExecutionResult,
        "ExecutionRoute": ModuleExecutionRoute,
        "OrderManager": ModuleOrderManager,
        "OrderSide": ModuleOrderSide,
        "OrderState": ModuleOrderState,
        "OrderStatus": ModuleOrderStatus,
        "OrderTracker": ModuleOrderTracker,
        "PaperTrade": ModulePaperTrade,
        "PaperTradeSide": ModulePaperTradeSide,
        "PaperTradingEngine": ModulePaperTradingEngine,
        "PortfolioManager": ModulePortfolioManager,
        "PortfolioState": ModulePortfolioState,
        "PortfolioSynchronizer": ModulePortfolioSynchronizer,
        "Position": ModulePosition,
        "PositionManager": ModulePositionManager,
        "RouteCandidate": ModuleRouteCandidate,
        "RoutingDecision": ModuleRoutingDecision,
        "SlippageCalculator": ModuleSlippageCalculator,
        "SlippageResult": ModuleSlippageResult,
        "SmartRouter": ModuleSmartRouter,
    }

    for name, original in expected.items():
        assert getattr(execution, name) is original


def test_wildcard_import_contains_only_public_api() -> None:
    namespace: dict[str, object] = {}

    exec(
        "from src.execution import *",
        {},
        namespace,
    )

    assert set(namespace) == set(
        EXPECTED_EXPORTS
    )


def test_reload_preserves_export_contract() -> None:
    reloaded = importlib.reload(execution)

    assert reloaded.__all__ == EXPECTED_EXPORTS

    for name in EXPECTED_EXPORTS:
        assert hasattr(reloaded, name)


def test_internal_helper_names_are_not_exported() -> None:
    forbidden = {
        "Clock",
        "Executor",
        "RLock",
        "deepcopy",
        "isfinite",
    }

    assert forbidden.isdisjoint(
        execution.__all__
    )