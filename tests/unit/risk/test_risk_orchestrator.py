import pytest

from src.risk.circuit_breaker import CircuitBreaker
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
def kill_switch():

    return KillSwitch()


@pytest.fixture
def circuit_breaker():

    return CircuitBreaker(
        max_consecutive_losses=3,
        cooldown_minutes=30,
    )


@pytest.fixture
def drawdown_guard():

    return DrawdownGuard(
        max_drawdown=0.15,
    )


@pytest.fixture
def portfolio_guard():

    return PortfolioGuard(
        max_positions=5,
        max_portfolio_risk=0.05,
        max_daily_loss=0.03,
        max_margin_usage=0.80,
    )


@pytest.fixture
def pre_trade_validator():

    return PreTradeValidator(
        max_position_size=100,
        max_leverage=10,
    )


@pytest.fixture
def orchestrator(
    kill_switch,
    circuit_breaker,
    drawdown_guard,
    portfolio_guard,
    pre_trade_validator,
):

    return RiskOrchestrator(
        kill_switch=kill_switch,
        circuit_breaker=circuit_breaker,
        drawdown_guard=drawdown_guard,
        portfolio_guard=portfolio_guard,
        pre_trade_validator=pre_trade_validator,
    )


def make_portfolio(**overrides):

    data = {
        "balance": 10_000.0,
        "equity": 10_000.0,
        "used_margin": 1_000.0,
        "open_positions": 2,
        "daily_loss": 0.01,
        "total_risk": 0.02,
    }

    data.update(overrides)

    return PortfolioState(**data)


def valid_trade_kwargs():

    return {
        "portfolio": make_portfolio(),
        "position_size": 10.0,
        "leverage": 2.0,
        "entry_price": 100.0,
        "stop_loss": 95.0,
    }


def test_valid_trade_is_approved(
    orchestrator,
):

    assert orchestrator.validate_trade(
        **valid_trade_kwargs()
    ) is True


def test_valid_trade_evaluation_is_approved(
    orchestrator,
):

    result = orchestrator.evaluate_trade(
        **valid_trade_kwargs()
    )

    assert isinstance(
        result,
        RiskEvaluation,
    )

    assert result.approved is True

    assert result.decision == (
        RiskDecision.APPROVED
    )

    assert result.reason == ""


def test_kill_switch_has_highest_priority(
    orchestrator,
    kill_switch,
):

    kill_switch.activate(
        "Emergency shutdown"
    )

    result = orchestrator.evaluate_trade(
        **valid_trade_kwargs()
    )

    assert result.approved is False

    assert result.decision == (
        RiskDecision.KILL_SWITCH
    )

    assert result.reason == (
        "Emergency shutdown"
    )


def test_circuit_breaker_rejects_trade(
    orchestrator,
    circuit_breaker,
):

    circuit_breaker.register_trade(-1)

    circuit_breaker.register_trade(-1)

    circuit_breaker.register_trade(-1)

    result = orchestrator.evaluate_trade(
        **valid_trade_kwargs()
    )

    assert result.approved is False

    assert result.decision == (
        RiskDecision.CIRCUIT_BREAKER
    )


def test_portfolio_rejection(
    orchestrator,
):

    result = orchestrator.evaluate_trade(
        **valid_trade_kwargs(
        )
        | {
            "portfolio": make_portfolio(
                open_positions=5,
            )
        }
    )

    assert result.approved is False

    assert result.decision == (
        RiskDecision.PORTFOLIO_REJECTED
    )


def test_position_size_rejection(
    orchestrator,
):

    result = orchestrator.evaluate_trade(
        **valid_trade_kwargs(
        )
        | {
            "position_size": 101.0,
        }
    )

    assert result.approved is False

    assert result.decision == (
        RiskDecision.TRADE_REJECTED
    )

    assert (
        "Position size"
        in result.reason
    )


def test_leverage_rejection(
    orchestrator,
):

    result = orchestrator.evaluate_trade(
        **valid_trade_kwargs(
        )
        | {
            "leverage": 11.0,
        }
    )

    assert result.approved is False

    assert result.decision == (
        RiskDecision.TRADE_REJECTED
    )

    assert (
        "Leverage"
        in result.reason
    )


def test_invalid_stop_loss_rejection(
    orchestrator,
):

    result = orchestrator.evaluate_trade(
        **valid_trade_kwargs(
        )
        | {
            "entry_price": 100.0,
            "stop_loss": 100.0,
        }
    )

    assert result.approved is False

    assert result.decision == (
        RiskDecision.TRADE_REJECTED
    )

    assert (
        "Stop loss"
        in result.reason
    )


def test_validate_trade_matches_evaluation(
    orchestrator,
):

    kwargs = valid_trade_kwargs()

    evaluation = (
        orchestrator.evaluate_trade(
            **kwargs
        )
    )

    validation = (
        orchestrator.validate_trade(
            **kwargs
        )
    )

    assert validation is (
        evaluation.approved
    )


def test_portfolio_rejection_precedes_position_rejection(
    orchestrator,
):

    result = orchestrator.evaluate_trade(
        **valid_trade_kwargs(
        )
        | {
            "portfolio": make_portfolio(
                open_positions=5,
            ),
            "position_size": 101.0,
        }
    )

    assert result.decision == (
        RiskDecision.PORTFOLIO_REJECTED
    )


def test_kill_switch_precedes_circuit_breaker(
    orchestrator,
    kill_switch,
    circuit_breaker,
):

    kill_switch.activate(
        "Manual stop"
    )

    circuit_breaker.register_trade(-1)

    circuit_breaker.register_trade(-1)

    circuit_breaker.register_trade(-1)

    result = orchestrator.evaluate_trade(
        **valid_trade_kwargs()
    )

    assert result.decision == (
        RiskDecision.KILL_SWITCH
    )


def test_evaluation_is_immutable(
    orchestrator,
):

    result = orchestrator.evaluate_trade(
        **valid_trade_kwargs()
    )

    with pytest.raises(
        AttributeError,
    ):

        result.approved = False


def test_invalid_portfolio_type(
    orchestrator,
):

    kwargs = valid_trade_kwargs()

    kwargs["portfolio"] = None

    with pytest.raises(
        TypeError,
        match="portfolio must be a PortfolioState",
    ):

        orchestrator.evaluate_trade(
            **kwargs
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
def test_invalid_dependencies_are_rejected(
    dependency_name,
):

    dependencies = {
        "kill_switch": KillSwitch(),
        "circuit_breaker": CircuitBreaker(),
        "drawdown_guard": DrawdownGuard(),
        "portfolio_guard": PortfolioGuard(),
        "pre_trade_validator": PreTradeValidator(
            max_position_size=100,
            max_leverage=10,
        ),
    }

    dependencies[
        dependency_name
    ] = None

    with pytest.raises(
        TypeError,
    ):

        RiskOrchestrator(
            **dependencies
        )


def test_result_types(
    orchestrator,
):

    result = orchestrator.evaluate_trade(
        **valid_trade_kwargs()
    )

    assert isinstance(
        result.approved,
        bool,
    )

    assert isinstance(
        result.decision,
        RiskDecision,
    )

    assert isinstance(
        result.reason,
        str,
    )