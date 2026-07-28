from datetime import UTC, datetime

from src.decision.recorded import DecisionOutcome, DecisionService
from src.risk.circuit_breaker import CircuitBreaker
from src.risk.drawdown_guard import DrawdownGuard
from src.risk.kill_switch import KillSwitch
from src.risk.portfolio_guard import PortfolioGuard, PortfolioState
from src.risk.pre_trade_validator import PreTradeValidator
from src.risk.risk_orchestrator import RiskOrchestrator
from src.strategy.models import ProposalDirection, TradeProposal


def decision_service(*, size: float = 1) -> DecisionService:
    risk = RiskOrchestrator(
        KillSwitch(),
        CircuitBreaker(),
        DrawdownGuard(),
        PortfolioGuard(),
        PreTradeValidator(max_position_size=10, max_leverage=2),
    )
    service = DecisionService(
        risk,
        portfolio=PortfolioState(10000, 10000, 0, 0, 0, 0),
        position_size=size,
        leverage=1,
    )
    service.initialize()
    service.start()
    return service


def proposal(
    direction: ProposalDirection = ProposalDirection.LONG,
    *,
    stop: float | None = 90,
    target: float | None = 120,
) -> TradeProposal:
    return TradeProposal(
        "proposal", "BTCUSDT", "recorded", "1m", direction, 100,
        stop, target, 0.75, "market-structure", "1.0.0",
        datetime(2026, 1, 1, tzinfo=UTC), ("EVIDENCE",),
    )


def test_approved_decision_is_deterministic() -> None:
    service = decision_service()
    first = service.evaluate(proposal())
    second = service.evaluate(proposal())
    assert first.outcome is DecisionOutcome.APPROVED
    assert first.to_json() == second.to_json()


def test_hold_is_not_an_error_or_sent_to_risk() -> None:
    result = decision_service().evaluate(
        proposal(ProposalDirection.HOLD, stop=None, target=None)
    )
    assert result.outcome is DecisionOutcome.HOLD


def test_invalid_price_relationship_is_rejected() -> None:
    result = decision_service().evaluate(proposal(stop=110, target=120))
    assert result.outcome is DecisionOutcome.REJECTED
    assert "INVALID_PRICE_RELATIONSHIP" in result.reason_codes


def test_frozen_risk_rejection_is_retained_as_code() -> None:
    result = decision_service(size=11).evaluate(proposal())
    assert result.outcome is DecisionOutcome.REJECTED
    assert "RISK_TRADE_REJECTED" in result.reason_codes
