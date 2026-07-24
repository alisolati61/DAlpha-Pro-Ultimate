"""Tests for the public risk package API."""

from __future__ import annotations

import src.risk as risk
from src.risk.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
)
from src.risk.drawdown_guard import (
    DrawdownGuard,
    DrawdownStatus,
)
from src.risk.in_trade_monitor import (
    InTradeDecision,
    InTradeMonitor,
    TradeDirection,
    TradeMonitorResult,
    TradeState,
)
from src.risk.kill_switch import (
    KillSwitch,
    KillSwitchState,
)
from src.risk.portfolio_guard import (
    PortfolioGuard,
    PortfolioState,
    PortfolioValidationResult,
)
from src.risk.position_sizer import (
    PositionSizeResult,
    PositionSizer,
)
from src.risk.pre_trade_validator import (
    PreTradeValidator,
    ValidationResult,
)
from src.risk.risk_manager import (
    RiskAssessment,
    RiskManager,
    RiskSettings,
    RiskStatus,
)
from src.risk.risk_orchestrator import (
    RiskDecision,
    RiskEvaluation,
    RiskOrchestrator,
)


EXPECTED_EXPORTS = (
    "CircuitBreaker",
    "CircuitBreakerState",
    "DrawdownGuard",
    "DrawdownStatus",
    "InTradeDecision",
    "InTradeMonitor",
    "KillSwitch",
    "KillSwitchState",
    "PortfolioGuard",
    "PortfolioState",
    "PortfolioValidationResult",
    "PositionSizeResult",
    "PositionSizer",
    "PreTradeValidator",
    "RiskAssessment",
    "RiskDecision",
    "RiskEvaluation",
    "RiskManager",
    "RiskOrchestrator",
    "RiskSettings",
    "RiskStatus",
    "TradeDirection",
    "TradeMonitorResult",
    "TradeState",
    "ValidationResult",
)


EXPECTED_OBJECTS = {
    "CircuitBreaker": CircuitBreaker,
    "CircuitBreakerState": CircuitBreakerState,
    "DrawdownGuard": DrawdownGuard,
    "DrawdownStatus": DrawdownStatus,
    "InTradeDecision": InTradeDecision,
    "InTradeMonitor": InTradeMonitor,
    "KillSwitch": KillSwitch,
    "KillSwitchState": KillSwitchState,
    "PortfolioGuard": PortfolioGuard,
    "PortfolioState": PortfolioState,
    "PortfolioValidationResult": (
        PortfolioValidationResult
    ),
    "PositionSizeResult": PositionSizeResult,
    "PositionSizer": PositionSizer,
    "PreTradeValidator": PreTradeValidator,
    "RiskAssessment": RiskAssessment,
    "RiskDecision": RiskDecision,
    "RiskEvaluation": RiskEvaluation,
    "RiskManager": RiskManager,
    "RiskOrchestrator": RiskOrchestrator,
    "RiskSettings": RiskSettings,
    "RiskStatus": RiskStatus,
    "TradeDirection": TradeDirection,
    "TradeMonitorResult": TradeMonitorResult,
    "TradeState": TradeState,
    "ValidationResult": ValidationResult,
}


def test_public_exports_are_explicit_and_stable() -> None:
    assert risk.__all__ == EXPECTED_EXPORTS


def test_public_exports_have_no_duplicates() -> None:
    assert len(risk.__all__) == len(
        set(risk.__all__)
    )


def test_every_public_export_exists() -> None:
    for export_name in EXPECTED_EXPORTS:
        assert hasattr(
            risk,
            export_name,
        ), f"missing risk export: {export_name}"


def test_public_exports_reference_original_objects() -> None:
    for export_name, expected_object in (
        EXPECTED_OBJECTS.items()
    ):
        assert (
            getattr(risk, export_name)
            is expected_object
        )


def test_wildcard_import_contains_only_public_exports() -> None:
    namespace: dict[str, object] = {}

    exec(
        "from src.risk import *",
        namespace,
    )

    imported_names = {
        name
        for name in namespace
        if not name.startswith("__")
    }

    assert imported_names == set(EXPECTED_EXPORTS)


def test_primary_engines_can_be_constructed() -> None:
    kill_switch = risk.KillSwitch()
    circuit_breaker = risk.CircuitBreaker()
    drawdown_guard = risk.DrawdownGuard()
    portfolio_guard = risk.PortfolioGuard()
    pre_trade_validator = risk.PreTradeValidator(
        max_position_size=100,
        max_leverage=10,
    )

    assert isinstance(
        kill_switch,
        KillSwitch,
    )
    assert isinstance(
        circuit_breaker,
        CircuitBreaker,
    )
    assert isinstance(
        drawdown_guard,
        DrawdownGuard,
    )
    assert isinstance(
        portfolio_guard,
        PortfolioGuard,
    )
    assert isinstance(
        pre_trade_validator,
        PreTradeValidator,
    )
    assert isinstance(
        risk.PositionSizer(),
        PositionSizer,
    )
    assert isinstance(
        risk.RiskManager(),
        RiskManager,
    )


def test_composed_risk_services_can_be_constructed() -> None:
    kill_switch = risk.KillSwitch()
    circuit_breaker = risk.CircuitBreaker()
    drawdown_guard = risk.DrawdownGuard()
    portfolio_guard = risk.PortfolioGuard()
    pre_trade_validator = risk.PreTradeValidator(
        max_position_size=100,
        max_leverage=10,
    )

    monitor = risk.InTradeMonitor(
        drawdown_guard=drawdown_guard,
        kill_switch=kill_switch,
    )

    orchestrator = risk.RiskOrchestrator(
        kill_switch=kill_switch,
        circuit_breaker=circuit_breaker,
        drawdown_guard=drawdown_guard,
        portfolio_guard=portfolio_guard,
        pre_trade_validator=pre_trade_validator,
    )

    assert isinstance(
        monitor,
        InTradeMonitor,
    )
    assert isinstance(
        orchestrator,
        RiskOrchestrator,
    )


def test_exported_enums_preserve_string_values() -> None:
    assert risk.RiskStatus.OK.value == "OK"
    assert (
        risk.RiskDecision.APPROVED.value
        == "APPROVED"
    )
    assert (
        risk.InTradeDecision.CONTINUE.value
        == "CONTINUE"
    )
    assert risk.TradeDirection.LONG.value == "LONG"


def test_internal_helpers_are_not_exported() -> None:
    assert "_validate_ratio" not in risk.__all__
    assert "_utc_now" not in risk.__all__
    assert "Clock" not in risk.__all__