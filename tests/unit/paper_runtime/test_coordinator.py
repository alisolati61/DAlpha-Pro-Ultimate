from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.execution.order_tracker import OrderStatus
from src.execution_intent.models import (
    ExecutionIntent,
    IntentOrderType,
    IntentReason,
    IntentSide,
    IntentStatus,
    IntentTimeInForce,
    OrderSpecification,
)
from src.paper_runtime import (
    PaperAccountSnapshot,
    PaperEventType,
    PaperExecutionCoordinator,
    PaperExecutionPolicy,
    PaperMarketEvent,
    PaperProtectionKind,
    PaperReason,
    PaperRuntimeError,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def account() -> PaperAccountSnapshot:
    return PaperAccountSnapshot(
        "10000", "10000", "10000", "0", "0", "0", "0", "0", 0
    )


def policy(*, cap: str = "1") -> PaperExecutionPolicy:
    return PaperExecutionPolicy("paper-v1", "10", "5", cap, "0.01", "2")


def intent(
    *,
    side: IntentSide = IntentSide.BUY,
    quantity: str = "2",
    status: IntentStatus = IntentStatus.READY,
) -> ExecutionIntent:
    if status is not IntentStatus.READY:
        return ExecutionIntent(
            "intent-1", "decision-1", status, None, None, None,
            None, None, None, None, None, None, None, None,
            (IntentReason.DECISION_HOLD,),
        )
    opposite = IntentSide.SELL if side is IntentSide.BUY else IntentSide.BUY
    entry_price = Decimal("100")
    stop = Decimal("90") if side is IntentSide.BUY else Decimal("110")
    target = Decimal("120") if side is IntentSide.BUY else Decimal("80")
    entry = OrderSpecification(
        side, IntentOrderType.LIMIT, entry_price, Decimal(quantity),
        IntentTimeInForce.GTC, False,
    )
    stop_spec = OrderSpecification(
        opposite, IntentOrderType.STOP, stop, Decimal(quantity),
        IntentTimeInForce.GTC, True,
    )
    target_spec = OrderSpecification(
        opposite, IntentOrderType.TAKE_PROFIT, target, Decimal(quantity),
        IntentTimeInForce.GTC, True,
    )
    return ExecutionIntent(
        "intent-1", "decision-1", status, "BTCUSDT", "recorded", "1m",
        entry, stop_spec, target_spec, "strategy", "1", Decimal("20"),
        "constraints-v1", T0, (IntentReason.INTENT_READY,),
    )


def event(
    sequence: int,
    *,
    price: str = "100",
    low: str = "99",
    high: str = "101",
    quantity: str = "10",
) -> PaperMarketEvent:
    return PaperMarketEvent(
        sequence, "BTCUSDT", T0 + timedelta(minutes=sequence),
        price, low, high, quantity,
    )


def running(*, cap: str = "1", hook=None) -> PaperExecutionCoordinator:
    service = PaperExecutionCoordinator(policy(cap=cap), account(), commit_hook=hook)
    service.initialize()
    service.start()
    return service


def test_no_action_intent_never_creates_order() -> None:
    service = running()
    result = service.submit_intent(
        intent(status=IntentStatus.NO_ACTION), source_sequence=1
    )
    assert not result.accepted
    assert result.reason is PaperReason.INTENT_NOT_READY
    assert service.account == account()


def test_submit_is_deterministic_idempotent_and_reserves_margin() -> None:
    service = running()
    first = service.submit_intent(intent(), source_sequence=1)
    second = service.submit_intent(intent(), source_sequence=1)
    assert first.accepted and second.accepted
    assert first.order == second.order
    assert first.order is not None
    assert first.order.status is OrderStatus.SENT
    assert service.account.reserved_margin == Decimal("100")
    assert [item.event_type for item in service.events] == [
        PaperEventType.ORDER_CREATED,
        PaperEventType.ORDER_ACCEPTED,
    ]
    with pytest.raises(FrozenInstanceError):
        first.order.status = OrderStatus.REJECTED  # type: ignore[misc]


def test_no_lookahead_and_deterministic_partial_then_full_fill() -> None:
    service = running()
    order = service.submit_intent(intent(), source_sequence=1).order
    assert order is not None
    same_event = service.advance_market(event(1))
    assert tuple(item.event_type for item in same_event) == (
        PaperEventType.MARKET_ACCEPTED,
    )
    first_events = service.advance_market(event(2))
    first = service.order(order.order_id)
    assert sum(
        item.event_type is PaperEventType.ENTRY_FILL
        for item in first_events
    ) == 1
    assert first.status is OrderStatus.PARTIALLY_FILLED
    assert first.filled_quantity == 1
    service.advance_market(event(3))
    final = service.order(order.order_id)
    assert final.status is OrderStatus.FILLED
    assert final.filled_quantity == 2
    assert final.average_fill_price == 100
    assert len(service.fills) == 2
    assert service.position("BTCUSDT").quantity == 2


def test_partial_cancel_releases_only_unfilled_reservation() -> None:
    service = running()
    order = service.submit_intent(intent(), source_sequence=1).order
    assert order is not None
    service.advance_market(event(2))
    result = service.cancel(order.order_id)
    assert result.order is not None
    assert result.order.status is OrderStatus.CANCELLED
    assert result.order.filled_quantity == 1
    assert service.account.reserved_margin == 0
    assert service.account.used_margin == 50
    assert service.position("BTCUSDT").quantity == 1
    assert {
        item.active_quantity for item in service.protections
    } == {Decimal("1")}


def test_unfilled_cancel_is_idempotent_and_cancels_inactive_protections() -> None:
    service = running()
    submission = service.submit_intent(intent(), source_sequence=1)
    assert submission.order is not None

    first = service.cancel(submission.order.order_id)
    second = service.cancel(submission.order.order_id)

    assert first.accepted
    assert not second.accepted
    assert second.reason is PaperReason.TERMINAL_ORDER
    assert service.account.reserved_margin == 0
    assert all(
        item.status is OrderStatus.CANCELLED
        for item in service.protections
    )


def test_long_take_profit_closes_without_reversal() -> None:
    service = running(cap="10")
    order = service.submit_intent(intent(), source_sequence=1).order
    assert order is not None
    service.advance_market(event(2))
    service.advance_market(event(3, price="120", low="119", high="121"))
    position = service.position("BTCUSDT")
    assert position.side == "FLAT"
    assert position.quantity == 0
    assert position.realized_pnl > 0
    assert service.account.exposure == 0
    protective = [fill for fill in service.fills if fill.protective]
    assert len(protective) == 1
    assert protective[0].trigger == "take_profit"
    assert protective[0].price < Decimal("120")
    assert protective[0].order_id != order.order_id
    assert protective[0].parent_order_id == order.order_id
    protections = {
        item.kind: item for item in service.protections
    }
    assert (
        protections[PaperProtectionKind.TAKE_PROFIT].status
        is OrderStatus.FILLED
    )
    assert (
        protections[PaperProtectionKind.STOP_LOSS].status
        is OrderStatus.CANCELLED
    )


def test_gap_stop_is_adverse_and_stop_wins_ambiguous_range() -> None:
    service = running(cap="10")
    service.submit_intent(intent(), source_sequence=1)
    service.advance_market(event(2))
    service.advance_market(
        event(3, price="80", low="79", high="121")
    )
    exit_fill = service.fills[-1]
    assert exit_fill.trigger == "stop_loss"
    assert exit_fill.price < 80


def test_partial_protective_exit_cancels_unfilled_entry_and_cannot_reverse() -> None:
    service = running(cap="1")
    submission = service.submit_intent(intent(), source_sequence=1)
    assert submission.order is not None
    service.advance_market(event(2))

    service.advance_market(
        event(3, price="120", low="119", high="121")
    )

    order_after = service.order(submission.order.order_id)
    assert order_after.status is OrderStatus.CANCELLED
    assert order_after.filled_quantity == Decimal("1")
    assert service.position("BTCUSDT").side == "FLAT"
    assert service.position("BTCUSDT").quantity == 0
    assert service.account.reserved_margin == 0
    service.advance_market(
        event(4, price="120", low="119", high="121")
    )
    assert len([fill for fill in service.fills if fill.protective]) == 1


def test_short_entry_and_take_profit_are_directionally_correct() -> None:
    service = running(cap="10")
    service.submit_intent(
        intent(side=IntentSide.SELL), source_sequence=1
    )
    service.advance_market(event(2))
    assert service.position("BTCUSDT").side == "SHORT"
    service.advance_market(event(3, price="80", low="79", high="81"))
    assert service.position("BTCUSDT").side == "FLAT"
    assert service.account.realized_pnl > 0
    assert service.fills[-1].price > Decimal("80")


def test_out_of_order_event_rolls_back_cursor_and_state() -> None:
    service = running()
    service.submit_intent(intent(), source_sequence=1)
    service.advance_market(event(2))
    before = service.export_checkpoint()
    with pytest.raises(PaperRuntimeError):
        service.advance_market(event(2))
    assert service.export_checkpoint() == before


def test_injected_commit_failure_rolls_back_every_component() -> None:
    def hook(stage: str) -> None:
        if stage == "balance_update":
            raise RuntimeError("C:\\secret\\credential.env")

    service = running(cap="10", hook=hook)
    service.submit_intent(intent(), source_sequence=1)
    before = service.export_checkpoint()
    with pytest.raises(PaperRuntimeError, match="Paper execution"):
        service.advance_market(event(2))
    assert service.export_checkpoint() == before
    assert service.fills == ()


def test_checkpoint_restore_is_byte_identical_and_retry_safe() -> None:
    original = running()
    submission = original.submit_intent(intent(), source_sequence=1)
    original.advance_market(event(2))
    checkpoint = original.export_checkpoint()
    restored = running()
    restored.restore_checkpoint(checkpoint)
    assert restored.export_checkpoint() == checkpoint
    retry = restored.submit_intent(intent(), source_sequence=1)
    assert retry.order == submission.order or retry.order == restored.order(
        submission.order.order_id  # type: ignore[union-attr]
    )
    restored.advance_market(event(3))
    assert len(restored.fills) == 2


def test_cancel_terminal_is_stable_noop_and_lifecycle_clears() -> None:
    service = running(cap="10")
    order = service.submit_intent(intent(), source_sequence=1).order
    assert order is not None
    service.advance_market(event(2))
    result = service.cancel(order.order_id)
    assert not result.accepted
    assert result.reason is PaperReason.TERMINAL_ORDER
    checkpoint = service.export_checkpoint()
    assert checkpoint.digest
    service.stop()
    assert service.fills == ()
    with pytest.raises(PaperRuntimeError):
        service.advance_market(event(3))


def test_service_definition_is_explicit() -> None:
    definition = PaperExecutionCoordinator(policy(), account()).definition()
    assert definition.service_id == "paper-execution"
    assert definition.dependencies == ("execution-intent", "market-data")


def test_conflicting_retry_fails_closed_without_state_change() -> None:
    service = running()
    service.submit_intent(intent(), source_sequence=1)
    before = service.export_checkpoint()

    result = service.submit_intent(intent(), source_sequence=2)

    assert not result.accepted
    assert result.reason is PaperReason.DUPLICATE_CONFLICT
    assert service.export_checkpoint() == before


def test_insufficient_balance_and_malformed_ready_do_not_mutate() -> None:
    small = PaperAccountSnapshot(
        "10", "10", "10", "0", "0", "0", "0", "0", 0
    )
    service = PaperExecutionCoordinator(policy(), small)
    service.initialize()
    service.start()
    before = service.export_checkpoint()

    rejected = service.submit_intent(intent(), source_sequence=1)

    assert not rejected.accepted
    assert rejected.reason is PaperReason.INSUFFICIENT_BALANCE
    assert service.export_checkpoint() == before

    malformed = intent()
    assert malformed.entry is not None
    object.__setattr__(
        malformed.entry, "order_type", IntentOrderType.STOP
    )
    with pytest.raises(PaperRuntimeError, match="Paper execution"):
        service.submit_intent(malformed, source_sequence=1)
    assert service.export_checkpoint() == before


def test_policy_constraints_binding_fails_closed() -> None:
    bound_policy = PaperExecutionPolicy(
        "paper-v1", "10", "5", "1", "0.01", "2", "other-constraints"
    )
    service = PaperExecutionCoordinator(bound_policy, account())
    service.initialize()
    service.start()
    before = service.export_checkpoint()

    with pytest.raises(PaperRuntimeError, match="Paper execution"):
        service.submit_intent(intent(), source_sequence=1)

    assert service.export_checkpoint() == before


def test_sequence_and_timestamp_must_both_advance_before_fill() -> None:
    service = running(cap="10")
    submission = service.submit_intent(intent(), source_sequence=1)
    assert submission.order is not None
    same_time = PaperMarketEvent(
        2, "BTCUSDT", T0, "100", "99", "101", "10"
    )

    service.advance_market(same_time)

    assert service.fills == ()
    later = PaperMarketEvent(
        3,
        "BTCUSDT",
        T0 + timedelta(minutes=1),
        "100",
        "99",
        "101",
        "10",
    )
    service.advance_market(later)
    assert service.order(submission.order.order_id).status is OrderStatus.FILLED


def test_unrealized_pnl_changes_only_from_explicit_market_event() -> None:
    service = running(cap="10")
    service.submit_intent(intent(), source_sequence=1)
    service.advance_market(event(2))
    before = service.position("BTCUSDT")

    service.advance_market(
        event(3, price="110", low="109", high="111", quantity="0")
    )

    after = service.position("BTCUSDT")
    assert before.unrealized_pnl == 0
    assert after.unrealized_pnl == Decimal("20")
    assert after.mark_price == Decimal("110")


def test_other_venue_event_cannot_fill_or_mark_position() -> None:
    service = running(cap="10")
    service.submit_intent(intent(), source_sequence=1)
    service.advance_market(event(2))
    before = service.position("BTCUSDT")
    foreign = PaperMarketEvent(
        3,
        "BTCUSDT",
        T0 + timedelta(minutes=3),
        "120",
        "89",
        "121",
        "10",
        "other-exchange",
        "1m",
    )

    service.advance_market(foreign)

    assert service.position("BTCUSDT") == before
    assert len([fill for fill in service.fills if fill.protective]) == 0
