"""Tests for central pre-execution risk orchestration."""

from dataclasses import FrozenInstanceError
from datetime import datetime
from math import inf, nan

import pytest

from src.risk.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
)
from src.risk.drawdown_guard import DrawdownGuard
from src.risk.kill_switch import KillSwitch
from src.risk.portfolio_guard import (
    PortfolioGuard,
    PortfolioState,
)
from src.risk.pre_trade_validator import (
    PreTradeValidator,
)
from src.risk.risk_orchestrator import (
    RiskDecision,
    RiskEvaluation,
    RiskOrchestrator,
)


@pytest.fixture
def kill_switch() -> KillSwitch:
    return KillSwitch()


@pytest.fixture
def circuit_breaker() -> CircuitBreaker:
    return CircuitBreaker(
        max_consecutive_losses=3,
        cooldown_minutes=30,
    )


@pytest.fixture
def drawdown_guard() -> DrawdownGuard:
    return DrawdownGuard(
        max_drawdown=0.15,
    )


@pytest.fixture
def portfolio_guard() -> PortfolioGuard:
    return PortfolioGuard(
        max_positions=5,
        max_portfolio_risk=0.05,
        max_daily_loss=0.03,
        max_margin_usage=0.80,
    )


@pytest.fixture
def pre_trade_validator() -> PreTradeValidator:
    return PreTradeValidator(
        max_position_size=100,
        max_leverage=10,
    )


@pytest.fixture
def orchestrator(
    kill_switch: KillSwitch,
    circuit_breaker: CircuitBreaker,
    drawdown_guard: DrawdownGuard,
    portfolio_guard: PortfolioGuard,
    pre_trade_validator: PreTradeValidator,
) -> RiskOrchestrator:
    return RiskOrchestrator(
        kill_switch=kill_switch,
        circuit_breaker=circuit_breaker,
        drawdown_guard=drawdown_guard,
        portfolio_guard=portfolio_guard,
        pre_trade_validator=pre_trade_validator,
    )


def make_portfolio(
    **overrides: object,
) -> PortfolioState:
    data: dict[str, object] = {
        "balance": 10_000.0,
        "equity": 10_000.0,
        "used_margin": 1_000.0,
        "open_positions": 2,
        "daily_loss": 0.01,
        "total_risk": 0.02,
    }
    data.update(overrides)

    return PortfolioState(
        **data,  # type: ignore[arg-type]
    )


def valid_trade_kwargs() -> dict[str, object]:
    return {
        "portfolio": make_portfolio(),
        "position_size": 10.0,
        "leverage": 2.0,
        "entry_price": 100.0,
        "stop_loss": 95.0,
    }


def test_valid_trade_is_approved(
    orchestrator: RiskOrchestrator,
) -> None:
    assert orchestrator.validate_trade(
        **valid_trade_kwargs(),  # type: ignore[arg-type]
    ) is True


def test_valid_trade_evaluation(
    orchestrator: RiskOrchestrator,
) -> None:
    result = orchestrator.evaluate_trade(
        **valid_trade_kwargs(),  # type: ignore[arg-type]
    )

    assert result == RiskEvaluation(
        approved=True,
        decision=RiskDecision.APPROVED,
        drawdown=0.0,
    )
    assert result.rejected is False


def test_validate_trade_returns_exact_bool(
    orchestrator: RiskOrchestrator,
) -> None:
    result = orchestrator.validate_trade(
        **valid_trade_kwargs(),  # type: ignore[arg-type]
    )

    assert type(result) is bool


def test_kill_switch_has_highest_priority(
    orchestrator: RiskOrchestrator,
    kill_switch: KillSwitch,
) -> None:
    kill_switch.activate(
        "Emergency shutdown"
    )

    result = orchestrator.evaluate_trade(
        portfolio=None,  # type: ignore[arg-type]
        position_size=nan,
        leverage=nan,
        entry_price=nan,
        stop_loss=nan,
    )

    assert result.approved is False
    assert result.decision is RiskDecision.KILL_SWITCH
    assert result.reason == "Emergency shutdown"
    assert result.drawdown is None


def test_circuit_breaker_rejects_trade(
    orchestrator: RiskOrchestrator,
    circuit_breaker: CircuitBreaker,
) -> None:
    for _ in range(3):
        circuit_breaker.register_trade(-1)

    result = orchestrator.evaluate_trade(
        **valid_trade_kwargs(),  # type: ignore[arg-type]
    )

    assert result.approved is False
    assert (
        result.decision
        is RiskDecision.CIRCUIT_BREAKER
    )
    assert result.reason == (
        "Maximum consecutive losses reached."
    )


def test_circuit_breaker_precedes_portfolio_type(
    orchestrator: RiskOrchestrator,
    circuit_breaker: CircuitBreaker,
) -> None:
    circuit_breaker.state = CircuitBreakerState(
        active=True,
        reason="Manual circuit stop",
        activated_at=None,
    )

    result = orchestrator.evaluate_trade(
        portfolio=None,  # type: ignore[arg-type]
        position_size=10,
        leverage=2,
        entry_price=100,
        stop_loss=95,
    )

    assert (
        result.decision
        is RiskDecision.CIRCUIT_BREAKER
    )
    assert result.reason == "Manual circuit stop"


def test_circuit_breaker_clock_error_fails_closed(
    kill_switch: KillSwitch,
    drawdown_guard: DrawdownGuard,
    portfolio_guard: PortfolioGuard,
    pre_trade_validator: PreTradeValidator,
) -> None:
    breaker = CircuitBreaker(
        clock=lambda: datetime(
            2026,
            7,
            24,
            10,
            0,
        )
    )
    breaker.state = CircuitBreakerState(
        active=True,
        reason="Testing",
        activated_at=None,
    )

    # A state without timestamp fails closed without consulting the clock.
    result = RiskOrchestrator(
        kill_switch=kill_switch,
        circuit_breaker=breaker,
        drawdown_guard=drawdown_guard,
        portfolio_guard=portfolio_guard,
        pre_trade_validator=pre_trade_validator,
    ).evaluate_trade(
        **valid_trade_kwargs(),  # type: ignore[arg-type]
    )

    assert (
        result.decision
        is RiskDecision.CIRCUIT_BREAKER
    )


def test_portfolio_rejection_preserves_reason(
    orchestrator: RiskOrchestrator,
) -> None:
    result = orchestrator.evaluate_trade(
        **(
            valid_trade_kwargs()
            | {
                "portfolio": make_portfolio(
                    open_positions=5,
                )
            }
        ),  # type: ignore[arg-type]
    )

    assert (
        result.decision
        is RiskDecision.PORTFOLIO_REJECTED
    )
    assert result.reason == (
        "Maximum open positions reached."
    )


def test_invalid_portfolio_data_is_rejected(
    orchestrator: RiskOrchestrator,
) -> None:
    result = orchestrator.evaluate_trade(
        **(
            valid_trade_kwargs()
            | {
                "portfolio": make_portfolio(
                    balance=0,
                )
            }
        ),  # type: ignore[arg-type]
    )

    assert (
        result.decision
        is RiskDecision.PORTFOLIO_REJECTED
    )
    assert result.reason == (
        "Balance must be greater than zero."
    )


def test_drawdown_below_limit_is_approved(
    orchestrator: RiskOrchestrator,
) -> None:
    result = orchestrator.evaluate_trade(
        **(
            valid_trade_kwargs()
            | {
                "portfolio": make_portfolio(
                    equity=8_501.0,
                )
            }
        ),  # type: ignore[arg-type]
    )

    assert result.approved is True
    assert result.drawdown == 0.1499


def test_drawdown_at_limit_is_rejected(
    orchestrator: RiskOrchestrator,
) -> None:
    result = orchestrator.evaluate_trade(
        **(
            valid_trade_kwargs()
            | {
                "portfolio": make_portfolio(
                    equity=8_500.0,
                )
            }
        ),  # type: ignore[arg-type]
    )

    assert (
        result.decision
        is RiskDecision.DRAWDOWN_REJECTED
    )
    assert result.reason == (
        "Maximum drawdown reached or exceeded."
    )
    assert result.drawdown == 0.15


def test_drawdown_above_limit_is_rejected(
    orchestrator: RiskOrchestrator,
) -> None:
    result = orchestrator.evaluate_trade(
        **(
            valid_trade_kwargs()
            | {
                "portfolio": make_portfolio(
                    equity=8_000.0,
                )
            }
        ),  # type: ignore[arg-type]
    )

    assert (
        result.decision
        is RiskDecision.DRAWDOWN_REJECTED
    )
    assert result.drawdown == 0.2


def test_equity_above_balance_has_zero_drawdown(
    orchestrator: RiskOrchestrator,
) -> None:
    result = orchestrator.evaluate_trade(
        **(
            valid_trade_kwargs()
            | {
                "portfolio": make_portfolio(
                    equity=12_000.0,
                )
            }
        ),  # type: ignore[arg-type]
    )

    assert result.approved is True
    assert result.drawdown == 0.0


def test_position_size_rejection(
    orchestrator: RiskOrchestrator,
) -> None:
    result = orchestrator.evaluate_trade(
        **(
            valid_trade_kwargs()
            | {
                "position_size": 101.0,
            }
        ),  # type: ignore[arg-type]
    )

    assert result.decision is RiskDecision.TRADE_REJECTED
    assert result.reason == (
        "Position size exceeds maximum allowed."
    )
    assert result.drawdown == 0.0


def test_leverage_rejection(
    orchestrator: RiskOrchestrator,
) -> None:
    result = orchestrator.evaluate_trade(
        **(
            valid_trade_kwargs()
            | {
                "leverage": 11.0,
            }
        ),  # type: ignore[arg-type]
    )

    assert result.decision is RiskDecision.TRADE_REJECTED
    assert result.reason == (
        "Leverage exceeds maximum allowed."
    )


def test_stop_loss_rejection(
    orchestrator: RiskOrchestrator,
) -> None:
    result = orchestrator.evaluate_trade(
        **(
            valid_trade_kwargs()
            | {
                "stop_loss": 100.0,
            }
        ),  # type: ignore[arg-type]
    )

    assert result.decision is RiskDecision.TRADE_REJECTED
    assert result.reason == (
        "Stop loss cannot equal entry price."
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "position_size",
            nan,
        ),
        (
            "leverage",
            inf,
        ),
        (
            "entry_price",
            True,
        ),
        (
            "stop_loss",
            "95",
        ),
    ],
)
def test_invalid_trade_inputs_are_rejections(
    orchestrator: RiskOrchestrator,
    field: str,
    value: object,
) -> None:
    result = orchestrator.evaluate_trade(
        **(
            valid_trade_kwargs()
            | {
                field: value,
            }
        ),  # type: ignore[arg-type]
    )

    assert result.decision is RiskDecision.TRADE_REJECTED


def test_validate_trade_matches_evaluation(
    orchestrator: RiskOrchestrator,
) -> None:
    kwargs = valid_trade_kwargs()

    evaluation = orchestrator.evaluate_trade(
        **kwargs,  # type: ignore[arg-type]
    )
    validation = orchestrator.validate_trade(
        **kwargs,  # type: ignore[arg-type]
    )

    assert validation is evaluation.approved


def test_portfolio_precedes_drawdown(
    orchestrator: RiskOrchestrator,
) -> None:
    result = orchestrator.evaluate_trade(
        **(
            valid_trade_kwargs()
            | {
                "portfolio": make_portfolio(
                    balance=0,
                    equity=0,
                ),
            }
        ),  # type: ignore[arg-type]
    )

    assert (
        result.decision
        is RiskDecision.PORTFOLIO_REJECTED
    )


def test_drawdown_precedes_trade_rejection(
    orchestrator: RiskOrchestrator,
) -> None:
    result = orchestrator.evaluate_trade(
        **(
            valid_trade_kwargs()
            | {
                "portfolio": make_portfolio(
                    equity=8_000.0,
                ),
                "position_size": 101.0,
            }
        ),  # type: ignore[arg-type]
    )

    assert (
        result.decision
        is RiskDecision.DRAWDOWN_REJECTED
    )


def test_portfolio_precedes_trade_rejection(
    orchestrator: RiskOrchestrator,
) -> None:
    result = orchestrator.evaluate_trade(
        **(
            valid_trade_kwargs()
            | {
                "portfolio": make_portfolio(
                    open_positions=5,
                ),
                "position_size": 101.0,
            }
        ),  # type: ignore[arg-type]
    )

    assert (
        result.decision
        is RiskDecision.PORTFOLIO_REJECTED
    )


def test_kill_switch_precedes_circuit_breaker(
    orchestrator: RiskOrchestrator,
    kill_switch: KillSwitch,
    circuit_breaker: CircuitBreaker,
) -> None:
    kill_switch.activate("Manual stop")

    for _ in range(3):
        circuit_breaker.register_trade(-1)

    result = orchestrator.evaluate_trade(
        **valid_trade_kwargs(),  # type: ignore[arg-type]
    )

    assert result.decision is RiskDecision.KILL_SWITCH


def test_invalid_portfolio_type(
    orchestrator: RiskOrchestrator,
) -> None:
    kwargs = valid_trade_kwargs()
    kwargs["portfolio"] = None

    with pytest.raises(
        TypeError,
        match="portfolio must be a PortfolioState",
    ):
        orchestrator.evaluate_trade(
            **kwargs,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "dependency_name",
    [
        "kill_switch",
        "circuit_breaker",
        "drawdown_guard",
        "portfolio_guard",
        "pre_trade_validator",
    ],
)
@pytest.mark.parametrize(
    "invalid_dependency",
    [
        None,
        object(),
    ],
)
def test_invalid_dependencies_are_rejected(
    dependency_name: str,
    invalid_dependency: object,
) -> None:
    dependencies: dict[str, object] = {
        "kill_switch": KillSwitch(),
        "circuit_breaker": CircuitBreaker(),
        "drawdown_guard": DrawdownGuard(),
        "portfolio_guard": PortfolioGuard(),
        "pre_trade_validator": (
            PreTradeValidator(
                max_position_size=100,
                max_leverage=10,
            )
        ),
    }
    dependencies[dependency_name] = invalid_dependency

    with pytest.raises(TypeError):
        RiskOrchestrator(
            **dependencies,  # type: ignore[arg-type]
        )


def test_dependencies_are_preserved(
    kill_switch: KillSwitch,
    circuit_breaker: CircuitBreaker,
    drawdown_guard: DrawdownGuard,
    portfolio_guard: PortfolioGuard,
    pre_trade_validator: PreTradeValidator,
) -> None:
    orchestrator = RiskOrchestrator(
        kill_switch=kill_switch,
        circuit_breaker=circuit_breaker,
        drawdown_guard=drawdown_guard,
        portfolio_guard=portfolio_guard,
        pre_trade_validator=pre_trade_validator,
    )

    assert orchestrator.kill_switch is kill_switch
    assert orchestrator.circuit_breaker is circuit_breaker
    assert orchestrator.drawdown_guard is drawdown_guard
    assert orchestrator.portfolio_guard is portfolio_guard
    assert (
        orchestrator.pre_trade_validator
        is pre_trade_validator
    )


def test_evaluation_is_immutable(
    orchestrator: RiskOrchestrator,
) -> None:
    result = orchestrator.evaluate_trade(
        **valid_trade_kwargs(),  # type: ignore[arg-type]
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        result.approved = False  # type: ignore[misc]


def test_result_types(
    orchestrator: RiskOrchestrator,
) -> None:
    result = orchestrator.evaluate_trade(
        **valid_trade_kwargs(),  # type: ignore[arg-type]
    )

    assert type(result.approved) is bool
    assert isinstance(result.decision, RiskDecision)
    assert type(result.reason) is str
    assert type(result.drawdown) is float


@pytest.mark.parametrize(
    "approved",
    [
        1,
        "True",
        None,
    ],
)
def test_evaluation_rejects_non_bool_approved(
    approved: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="approved must be a bool",
    ):
        RiskEvaluation(
            approved=approved,  # type: ignore[arg-type]
            decision=RiskDecision.APPROVED,
        )


def test_evaluation_rejects_invalid_decision_type() -> None:
    with pytest.raises(
        TypeError,
        match="decision must be a RiskDecision",
    ):
        RiskEvaluation(
            approved=True,
            decision="APPROVED",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    (
        "approved",
        "decision",
        "reason",
        "message",
    ),
    [
        (
            False,
            RiskDecision.APPROVED,
            "",
            "APPROVED decision must be approved",
        ),
        (
            True,
            RiskDecision.APPROVED,
            "Unexpected",
            "APPROVED decision must not have a reason",
        ),
        (
            True,
            RiskDecision.KILL_SWITCH,
            "Emergency",
            "rejection decision cannot be approved",
        ),
        (
            False,
            RiskDecision.KILL_SWITCH,
            "",
            "rejection decision requires a reason",
        ),
    ],
)
def test_evaluation_invariants(
    approved: bool,
    decision: RiskDecision,
    reason: str,
    message: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=message,
    ):
        RiskEvaluation(
            approved=approved,
            decision=decision,
            reason=reason,
        )


def test_evaluation_reason_is_stripped() -> None:
    result = RiskEvaluation(
        approved=False,
        decision=RiskDecision.KILL_SWITCH,
        reason="  Emergency  ",
    )

    assert result.reason == "Emergency"


@pytest.mark.parametrize(
    "reason",
    [
        None,
        1,
        True,
        object(),
    ],
)
def test_evaluation_rejects_non_string_reason(
    reason: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="reason must be a string",
    ):
        RiskEvaluation(
            approved=False,
            decision=RiskDecision.KILL_SWITCH,
            reason=reason,  # type: ignore[arg-type]
        )


def test_evaluation_reason_length_is_bounded() -> None:
    with pytest.raises(
        ValueError,
        match="reason must not exceed 500 characters",
    ):
        RiskEvaluation(
            approved=False,
            decision=RiskDecision.KILL_SWITCH,
            reason="x" * 501,
        )


@pytest.mark.parametrize(
    "drawdown",
    [
        -0.01,
        1.01,
        nan,
        inf,
        -inf,
    ],
)
def test_evaluation_rejects_invalid_drawdown(
    drawdown: float,
) -> None:
    with pytest.raises(ValueError):
        RiskEvaluation(
            approved=False,
            decision=RiskDecision.DRAWDOWN_REJECTED,
            reason="Drawdown",
            drawdown=drawdown,
        )


@pytest.mark.parametrize(
    "drawdown",
    [
        True,
        "0.1",
        object(),
    ],
)
def test_evaluation_rejects_non_numeric_drawdown(
    drawdown: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="drawdown must be a number",
    ):
        RiskEvaluation(
            approved=False,
            decision=RiskDecision.DRAWDOWN_REJECTED,
            reason="Drawdown",
            drawdown=drawdown,  # type: ignore[arg-type]
        )