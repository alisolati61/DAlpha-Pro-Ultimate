from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Callable

import pytest

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
    PaperExecutionCoordinator,
    PaperExecutionPolicy,
    PaperExecutionReport,
    PaperMarketEvent,
    PaperReconciler,
    ReconciliationReason,
    ReconciliationStatus,
)

_SOURCE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def _account() -> PaperAccountSnapshot:
    return PaperAccountSnapshot(
        "10000",
        "10000",
        "10000",
        "0",
        "0",
        "0",
        "0",
        "0",
        0,
    )


def _policy() -> PaperExecutionPolicy:
    return PaperExecutionPolicy(
        "paper-reconciliation-v1",
        "0",
        "0",
        "10",
        "0.01",
        "2",
    )


def _intent() -> ExecutionIntent:
    quantity = Decimal("2")
    entry = OrderSpecification(
        IntentSide.BUY,
        IntentOrderType.LIMIT,
        Decimal("100"),
        quantity,
        IntentTimeInForce.GTC,
        False,
    )
    stop = OrderSpecification(
        IntentSide.SELL,
        IntentOrderType.STOP,
        Decimal("90"),
        quantity,
        IntentTimeInForce.GTC,
        True,
    )
    target = OrderSpecification(
        IntentSide.SELL,
        IntentOrderType.TAKE_PROFIT,
        Decimal("120"),
        quantity,
        IntentTimeInForce.GTC,
        True,
    )
    return ExecutionIntent(
        "intent-reconciliation",
        "decision-reconciliation",
        IntentStatus.READY,
        "BTCUSDT",
        "recorded",
        "1m",
        entry,
        stop,
        target,
        "market-structure",
        "1.0.0",
        Decimal("20"),
        "constraints-v1",
        _SOURCE_TIME,
        (IntentReason.INTENT_READY,),
    )


def _market_event(
    sequence: int,
    *,
    price: str,
    low: str,
    high: str,
) -> PaperMarketEvent:
    return PaperMarketEvent(
        sequence,
        "BTCUSDT",
        _SOURCE_TIME + timedelta(minutes=sequence),
        price,
        low,
        high,
        "10",
    )


def _matched_report() -> PaperExecutionReport:
    coordinator = PaperExecutionCoordinator(_policy(), _account())
    coordinator.initialize()
    coordinator.start()
    submission = coordinator.submit_intent(
        _intent(),
        source_sequence=1,
    )
    assert submission.order is not None
    coordinator.advance_market(
        _market_event(2, price="100", low="99", high="101")
    )
    coordinator.advance_market(
        _market_event(3, price="120", low="119", high="121")
    )
    return coordinator.report(submission.order.order_id)


def _filled_quantity_mismatch(
    report: PaperExecutionReport,
) -> PaperExecutionReport:
    object.__setattr__(
        report.order,
        "filled_quantity",
        report.order.filled_quantity - Decimal("1"),
    )
    return report


def _average_price_mismatch(
    report: PaperExecutionReport,
) -> PaperExecutionReport:
    return replace(
        report,
        order=replace(
            report.order,
            average_fill_price=report.order.average_fill_price + Decimal("1"),
        ),
    )


def _fee_mismatch(
    report: PaperExecutionReport,
) -> PaperExecutionReport:
    return replace(
        report,
        order=replace(report.order, fees=report.order.fees + Decimal("1")),
    )


def _position_quantity_mismatch(
    report: PaperExecutionReport,
) -> PaperExecutionReport:
    return replace(
        report,
        position=replace(
            report.position,
            side="LONG",
            quantity=Decimal("1"),
        ),
    )


def _realized_pnl_mismatch(
    report: PaperExecutionReport,
) -> PaperExecutionReport:
    return replace(
        report,
        position=replace(
            report.position,
            realized_pnl=report.position.realized_pnl + Decimal("1"),
        ),
    )


def _balance_mismatch(
    report: PaperExecutionReport,
) -> PaperExecutionReport:
    return replace(
        report,
        account=replace(
            report.account,
            balance=report.account.balance + Decimal("1"),
        ),
    )


def _exposure_mismatch(
    report: PaperExecutionReport,
) -> PaperExecutionReport:
    return replace(
        report,
        account=replace(
            report.account,
            exposure=report.account.exposure + Decimal("1"),
        ),
    )


def _duplicate_fill_id(
    report: PaperExecutionReport,
) -> PaperExecutionReport:
    return replace(report, fills=(*report.fills, report.fills[0]))


def _orphan_protective_order(
    report: PaperExecutionReport,
) -> PaperExecutionReport:
    protective_index = next(
        index for index, fill in enumerate(report.fills) if fill.protective
    )
    fills = list(report.fills)
    fills[protective_index] = replace(
        fills[protective_index],
        order_id="orphan-protective-order",
    )
    return replace(report, fills=tuple(fills))


def _over_close(
    report: PaperExecutionReport,
) -> PaperExecutionReport:
    protective_index = next(
        index for index, fill in enumerate(report.fills) if fill.protective
    )
    fills = list(report.fills)
    fills[protective_index] = replace(
        fills[protective_index],
        quantity=report.order.filled_quantity + Decimal("1"),
    )
    return replace(report, fills=tuple(fills))


def _missing_ledger_event(
    report: PaperExecutionReport,
) -> PaperExecutionReport:
    missing_fill_id = report.fills[0].fill_id
    return replace(
        report,
        events=tuple(
            event
            for event in report.events
            if event.fill_id != missing_fill_id
        ),
    )


_ReportMutation = Callable[[PaperExecutionReport], PaperExecutionReport]


@pytest.mark.parametrize(
    ("mutation", "reason"),
    (
        (
            _filled_quantity_mismatch,
            ReconciliationReason.FILLED_QUANTITY_MISMATCH,
        ),
        (
            _filled_quantity_mismatch,
            ReconciliationReason.REMAINING_QUANTITY_MISMATCH,
        ),
        (
            _average_price_mismatch,
            ReconciliationReason.AVERAGE_PRICE_MISMATCH,
        ),
        (_fee_mismatch, ReconciliationReason.FEE_MISMATCH),
        (
            _position_quantity_mismatch,
            ReconciliationReason.POSITION_QUANTITY_MISMATCH,
        ),
        (
            _realized_pnl_mismatch,
            ReconciliationReason.REALIZED_PNL_MISMATCH,
        ),
        (_balance_mismatch, ReconciliationReason.BALANCE_MISMATCH),
        (_exposure_mismatch, ReconciliationReason.EXPOSURE_MISMATCH),
        (_duplicate_fill_id, ReconciliationReason.DUPLICATE_FILL_ID),
        (
            _orphan_protective_order,
            ReconciliationReason.ORPHAN_PROTECTIVE_ORDER,
        ),
        (_over_close, ReconciliationReason.OVER_CLOSE),
        (
            _missing_ledger_event,
            ReconciliationReason.MISSING_LEDGER_EVENT,
        ),
    ),
)
def test_reconciler_detects_each_stable_mismatch_reason(
    mutation: _ReportMutation,
    reason: ReconciliationReason,
) -> None:
    report = mutation(_matched_report())

    result = PaperReconciler().reconcile(report)

    assert result.status is ReconciliationStatus.MISMATCH
    assert reason in result.reasons
    assert result.reasons == tuple(
        sorted(set(result.reasons), key=lambda item: item.value)
    )


def test_reconciler_matches_immutable_ledger_derived_state() -> None:
    report = _matched_report()
    serialized_before = report.to_json()

    first = PaperReconciler().reconcile(report)
    second = PaperReconciler().reconcile(report)

    assert first == second
    assert first.status is ReconciliationStatus.MATCHED
    assert first.reasons == (ReconciliationReason.MATCHED,)
    assert report.to_json() == serialized_before


def test_duplicate_ledger_event_is_detected_without_repair() -> None:
    original = _matched_report()
    corrupted = replace(
        original, events=(*original.events, original.events[-1])
    )
    serialized = corrupted.to_json()

    result = PaperReconciler().reconcile(corrupted)

    assert result.status is ReconciliationStatus.MISMATCH
    assert ReconciliationReason.DUPLICATE_LEDGER_EVENT in result.reasons
    assert corrupted.to_json() == serialized
