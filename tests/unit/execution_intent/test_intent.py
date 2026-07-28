from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.decision.recorded import DecisionOutcome, RecordedDecision
from src.execution_intent import (
    AccountExecutionSnapshot,
    ApprovedRiskSnapshot,
    ExecutionIntentService,
    ExecutionPolicy,
    InstrumentConstraints,
    IntentReason,
    IntentStatus,
)
from src.strategy.models import ProposalDirection, TradeProposal


def proposal(
    direction: ProposalDirection = ProposalDirection.LONG,
    *,
    entry: float = 100.07,
    stop: float | None = 95.03,
    target: float | None = 110.09,
) -> TradeProposal:
    return TradeProposal(
        "proposal-1", "BTCUSDT", "recorded", "1m", direction,
        entry, stop, target, 0.75, "market-structure", "1.0.0",
        datetime(2026, 1, 1, tzinfo=UTC), ("EVIDENCE",),
    )


def decision(
    outcome: DecisionOutcome = DecisionOutcome.APPROVED,
) -> RecordedDecision:
    return RecordedDecision("decision-1", "proposal-1", outcome, ("SOURCE",))


def account(**changes: object) -> AccountExecutionSnapshot:
    values: dict[str, object] = {
        "equity": "10000",
        "available_balance": "10000",
        "current_exposure": "0",
        "open_position_quantity": "0",
        "version": "account-v1",
    }
    values.update(changes)
    return AccountExecutionSnapshot(**values)  # type: ignore[arg-type]


def constraints(**changes: object) -> InstrumentConstraints:
    values: dict[str, object] = {
        "symbol": "BTCUSDT",
        "exchange": "recorded",
        "price_tick": "0.1",
        "quantity_step": "0.01",
        "minimum_quantity": "0.01",
        "minimum_notional": "10",
        "maximum_quantity": "100",
        "constraints_id": "instrument-v1",
    }
    values.update(changes)
    return InstrumentConstraints(**values)  # type: ignore[arg-type]


def policy(**changes: object) -> ExecutionPolicy:
    values: dict[str, object] = {
        "risk_percent": "1",
        "leverage": "2",
        "maximum_exposure_ratio": "1",
    }
    values.update(changes)
    return ExecutionPolicy(**values)  # type: ignore[arg-type]


def risk_approval(**changes: object) -> ApprovedRiskSnapshot:
    values: dict[str, object] = {
        "decision_id": "decision-1",
        "maximum_quantity": "100",
        "risk_percent": "1",
        "leverage": "2",
        "risk_reference": "risk-v1",
    }
    values.update(changes)
    return ApprovedRiskSnapshot(**values)  # type: ignore[arg-type]


def running() -> ExecutionIntentService:
    service = ExecutionIntentService()
    service.initialize()
    service.start()
    return service


def test_ready_intent_is_deterministic_immutable_and_conservative() -> None:
    service = running()
    first = service.construct(
        decision(), proposal=proposal(), account=account(),
        risk_approval=risk_approval(),
        constraints=constraints(), policy=policy(),
    )
    second = service.construct(
        decision(), proposal=proposal(), account=account(),
        risk_approval=risk_approval(),
        constraints=constraints(), policy=policy(),
    )
    assert first is second
    assert first.status is IntentStatus.READY
    assert first.to_json() == second.to_json()
    assert first.entry is not None and first.entry.price == Decimal("100")
    assert first.stop_loss is not None and first.stop_loss.price == Decimal("95.1")
    assert first.take_profit is not None
    assert first.take_profit.price == Decimal("110")
    assert first.entry.quantity % Decimal("0.01") == 0
    with pytest.raises(FrozenInstanceError):
        first.status = IntentStatus.BLOCKED  # type: ignore[misc]


def test_short_prices_are_conservatively_normalized() -> None:
    short = proposal(
        ProposalDirection.SHORT, entry=100.03, stop=105.08, target=90.02
    )
    result = running().construct(
        decision(), proposal=short, account=account(),
        risk_approval=risk_approval(),
        constraints=constraints(), policy=policy(),
    )
    assert result.status is IntentStatus.READY
    assert result.entry is not None and result.entry.price == Decimal("100.1")
    assert result.stop_loss is not None and result.stop_loss.price == Decimal("105")
    assert result.take_profit is not None
    assert result.take_profit.price == Decimal("90.1")


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -1, "bad"])
def test_invalid_account_numbers_are_rejected(value: object) -> None:
    with pytest.raises(ValueError):
        account(equity=value)


def test_hold_and_rejected_are_no_action() -> None:
    service = running()
    hold = service.construct(decision(DecisionOutcome.HOLD))
    rejected = service.construct(decision(DecisionOutcome.REJECTED))
    assert hold.status is IntentStatus.NO_ACTION
    assert hold.reason_codes == (IntentReason.DECISION_HOLD,)
    assert rejected.reason_codes == (IntentReason.DECISION_REJECTED,)


@pytest.mark.parametrize(
    ("account_changes", "constraint_changes", "expected"),
    [
        ({"available_balance": "1"}, {}, IntentReason.INSUFFICIENT_BALANCE),
        (
            {"current_exposure": "9999"},
            {},
            IntentReason.EXPOSURE_LIMIT,
        ),
        ({}, {"minimum_quantity": "50"}, IntentReason.QUANTITY_BELOW_MINIMUM),
        ({}, {"maximum_quantity": "1"}, IntentReason.QUANTITY_ABOVE_MAXIMUM),
        ({}, {"minimum_notional": "100000"}, IntentReason.NOTIONAL_BELOW_MINIMUM),
    ],
)
def test_sizing_failures_are_stable(
    account_changes: dict[str, object],
    constraint_changes: dict[str, object],
    expected: IntentReason,
) -> None:
    result = running().construct(
        decision(),
        proposal=proposal(),
        account=account(**account_changes),
        risk_approval=risk_approval(),
        constraints=constraints(**constraint_changes),
        policy=policy(),
    )
    assert result.status is IntentStatus.BLOCKED
    assert result.reason_codes == (expected,)


def test_normalization_that_collapses_protection_is_blocked() -> None:
    result = running().construct(
        decision(),
        proposal=proposal(entry=100.04, stop=100.03, target=100.05),
        account=account(),
        risk_approval=risk_approval(),
        constraints=constraints(price_tick="0.1"),
        policy=policy(),
    )
    assert result.reason_codes == (
        IntentReason.NORMALIZATION_INVALIDATED_PROTECTION,
    )


def test_zero_risk_distance_is_blocked() -> None:
    result = running().construct(
        decision(),
        proposal=proposal(entry=100, stop=100, target=110),
        account=account(),
        risk_approval=risk_approval(),
        constraints=constraints(),
        policy=policy(),
    )
    assert result.reason_codes == (IntentReason.INVALID_RISK_DISTANCE,)


def test_collaborator_failure_is_sanitized_and_atomic() -> None:
    class BrokenValidator:
        def validate(self, *args, **kwargs) -> None:
            raise RuntimeError("C:\\secret\\keys.env token=private")

    service = ExecutionIntentService(BrokenValidator())  # type: ignore[arg-type]
    service.initialize()
    service.start()
    result = service.construct(
        decision(), proposal=proposal(), account=account(),
        risk_approval=risk_approval(),
        constraints=constraints(), policy=policy(),
    )
    assert result.reason_codes == (
        IntentReason.EXECUTION_CONTRACT_INCOMPATIBLE,
    )
    assert "secret" not in result.to_json()
    assert service.accepted_count == 0


def test_duplicate_conflict_and_shutdown_clear() -> None:
    service = running()
    first = service.construct(
        decision(), proposal=proposal(), account=account(),
        risk_approval=risk_approval(),
        constraints=constraints(), policy=policy(),
    )
    conflict = service.construct(
        decision(), proposal=proposal(), account=account(version="account-v2"),
        risk_approval=risk_approval(),
        constraints=constraints(), policy=policy(),
    )
    assert first.status is IntentStatus.READY
    assert conflict.reason_codes == (IntentReason.DUPLICATE_CONFLICT,)
    assert service.accepted_count == 1
    service.stop()
    assert service.accepted_count == 0
    with pytest.raises(RuntimeError, match="unavailable"):
        service.construct(decision())


def test_mismatched_proposal_is_blocked() -> None:
    other = proposal()
    object.__setattr__(other, "proposal_id", "other")
    result = running().construct(
        decision(), proposal=other, account=account(),
        risk_approval=risk_approval(),
        constraints=constraints(), policy=policy(),
    )
    assert result.reason_codes == (IntentReason.INVALID_DECISION,)


def test_quantity_cannot_exceed_frozen_risk_approval() -> None:
    result = running().construct(
        decision(),
        proposal=proposal(),
        account=account(),
        risk_approval=risk_approval(maximum_quantity="1"),
        constraints=constraints(),
        policy=policy(),
    )
    assert result.reason_codes == (IntentReason.QUANTITY_ABOVE_MAXIMUM,)


def test_service_definition_is_explicit() -> None:
    definition = ExecutionIntentService().definition()
    assert definition.service_id == "execution-intent"
    assert definition.dependencies == ("decision",)
