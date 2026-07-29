from __future__ import annotations

import hashlib
import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Callable

import pytest

from src.execution.order_tracker import OrderStatus
from src.paper_runtime import (
    PaperAccountSnapshot,
    PaperCheckpoint,
    PaperEventType,
    PaperExecutionPolicy,
    PaperExecutionReport,
    PaperFill,
    PaperLedgerEvent,
    PaperMarketEvent,
    PaperOrderSnapshot,
    PaperPositionSnapshot,
    PaperReason,
    PaperSubmissionResult,
    ReconciliationReason,
    ReconciliationResult,
    ReconciliationStatus,
)
from src.paper_runtime.models import (
    account_mapping,
    canonical_json,
    fill_mapping,
    order_mapping,
    position_mapping,
    report_mapping,
)

NOW = datetime(2026, 7, 28, 12, 30, tzinfo=UTC)
SECRET = r"C:\Users\operator\.env:api_secret=do-not-leak"


def policy(**changes: object) -> PaperExecutionPolicy:
    values: dict[str, object] = {
        "policy_id": "paper-v1",
        "slippage_bps": "10.00",
        "fee_bps": "5.00",
        "maximum_fill_quantity": "2.00",
        "minimum_executable_quantity": "0.01",
        "leverage": "2.00",
    }
    values.update(changes)
    return PaperExecutionPolicy(**values)  # type: ignore[arg-type]


def market_event(**changes: object) -> PaperMarketEvent:
    values: dict[str, object] = {
        "sequence": 7,
        "symbol": "BTCUSDT",
        "timestamp": NOW,
        "price": "100.00",
        "low": "99.00",
        "high": "101.00",
        "available_quantity": "3.00",
    }
    values.update(changes)
    return PaperMarketEvent(**values)  # type: ignore[arg-type]


def order(**changes: object) -> PaperOrderSnapshot:
    values: dict[str, object] = {
        "order_id": "order-1",
        "intent_id": "intent-1",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "quantity": "2.00",
        "limit_price": "100.00",
        "stop_price": "90.00",
        "target_price": "120.00",
        "filled_quantity": "1.00",
        "average_fill_price": "100.00",
        "fees": "0.05",
        "status": OrderStatus.PARTIALLY_FILLED,
        "source_timestamp": NOW,
        "source_sequence": 6,
    }
    values.update(changes)
    return PaperOrderSnapshot(**values)  # type: ignore[arg-type]


def fill(**changes: object) -> PaperFill:
    values: dict[str, object] = {
        "fill_id": "fill-1",
        "order_id": "order-1",
        "intent_id": "intent-1",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "quantity": "1.00",
        "price": "100.00",
        "fee": "0.05",
        "market_sequence": 7,
        "market_timestamp": NOW,
        "protective": False,
        "trigger": "entry",
    }
    values.update(changes)
    return PaperFill(**values)  # type: ignore[arg-type]


def position(**changes: object) -> PaperPositionSnapshot:
    values: dict[str, object] = {
        "symbol": "BTCUSDT",
        "side": "LONG",
        "quantity": "1.00",
        "average_entry_price": "100.00",
        "realized_pnl": "0.00",
        "unrealized_pnl": "1.25",
        "mark_price": "101.25",
    }
    values.update(changes)
    return PaperPositionSnapshot(**values)  # type: ignore[arg-type]


def account(**changes: object) -> PaperAccountSnapshot:
    values: dict[str, object] = {
        "starting_balance": "10000.00",
        "balance": "9998.70",
        "available_balance": "9948.70",
        "reserved_margin": "0.00",
        "used_margin": "50.00",
        "fees_paid": "0.05",
        "realized_pnl": "-1.25",
        "exposure": "100.00",
        "version": 3,
    }
    values.update(changes)
    return PaperAccountSnapshot(**values)  # type: ignore[arg-type]


def ledger_event(**changes: object) -> PaperLedgerEvent:
    values: dict[str, object] = {
        "event_id": "event-1",
        "event_type": PaperEventType.ENTRY_FILL,
        "order_id": "order-1",
        "fill_id": "fill-1",
        "market_sequence": 7,
    }
    values.update(changes)
    return PaperLedgerEvent(**values)  # type: ignore[arg-type]


def report(**changes: object) -> PaperExecutionReport:
    values: dict[str, object] = {
        "order": order(),
        "fills": (fill(),),
        "position": position(),
        "account": account(),
        "events": (ledger_event(),),
    }
    values.update(changes)
    return PaperExecutionReport(**values)  # type: ignore[arg-type]


def checkpoint(
    payload: object | None = None,
    *,
    policy_id: str = "paper-v1",
    version: int = 3,
) -> PaperCheckpoint:
    selected = (
        {
            "account": {"balance": "9998.7", "version": version},
            "events": [],
            "policy_id": policy_id,
        }
        if payload is None
        else payload
    )
    payload_json = canonical_json(selected)
    digest = hashlib.sha256(
        f"{policy_id}:{version}:{payload_json}".encode()
    ).hexdigest()
    return PaperCheckpoint(policy_id, version, payload_json, digest)


@pytest.mark.parametrize(
    ("factory", "field", "replacement"),
    [
        (policy, "fee_bps", Decimal("1")),
        (market_event, "sequence", 8),
        (order, "status", OrderStatus.FILLED),
        (fill, "price", Decimal("101")),
        (position, "quantity", Decimal("2")),
        (account, "version", 4),
        (ledger_event, "event_id", "changed"),
        (
            lambda: PaperSubmissionResult(True, PaperReason.ACCEPTED, order()),
            "accepted",
            False,
        ),
        (report, "fills", ()),
        (
            lambda: ReconciliationResult(
                ReconciliationStatus.MATCHED,
                (ReconciliationReason.MATCHED,),
            ),
            "status",
            ReconciliationStatus.MISMATCH,
        ),
        (checkpoint, "digest", "0" * 64),
    ],
)
def test_public_contracts_are_frozen(
    factory: Callable[[], object],
    field: str,
    replacement: object,
) -> None:
    instance = factory()

    with pytest.raises(FrozenInstanceError):
        setattr(instance, field, replacement)


def test_decimal_fields_are_normalized_and_remaining_quantity_is_derived() -> None:
    selected_policy = policy()
    selected_order = order()

    assert selected_policy.slippage_bps == Decimal("1E+1")
    assert selected_policy.fee_bps == Decimal("5")
    assert selected_order.quantity == Decimal("2")
    assert selected_order.remaining_quantity == Decimal("1")


@pytest.mark.parametrize("invalid", [True, Decimal("NaN"), Decimal("Infinity")])
@pytest.mark.parametrize(
    "factory,field",
    [
        (policy, "slippage_bps"),
        (policy, "maximum_fill_quantity"),
        (market_event, "price"),
        (market_event, "available_quantity"),
        (order, "quantity"),
        (order, "fees"),
        (fill, "quantity"),
        (fill, "fee"),
        (position, "quantity"),
        (account, "balance"),
        (account, "realized_pnl"),
    ],
)
def test_numeric_fields_reject_bool_nan_and_infinity(
    factory: Callable[..., object],
    field: str,
    invalid: object,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        factory(**{field: invalid})


@pytest.mark.parametrize(
    ("factory", "field", "invalid"),
    [
        (policy, "slippage_bps", "-0.01"),
        (policy, "maximum_fill_quantity", "0"),
        (market_event, "sequence", True),
        (market_event, "sequence", -1),
        (market_event, "available_quantity", "-0.01"),
        (order, "source_sequence", True),
        (order, "source_sequence", -1),
        (fill, "market_sequence", True),
        (fill, "market_sequence", 1.5),
        (account, "version", True),
        (account, "version", 1.5),
    ],
)
def test_ranges_and_integer_fields_are_strict(
    factory: Callable[..., object],
    field: str,
    invalid: object,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        factory(**{field: invalid})


def test_signed_finite_pnl_is_supported_for_losses() -> None:
    selected_position = position(
        realized_pnl="-5.25",
        unrealized_pnl="-1.25",
    )
    selected_account = account(realized_pnl="-5.25")

    assert selected_position.realized_pnl == Decimal("-5.25")
    assert selected_position.unrealized_pnl == Decimal("-1.25")
    assert selected_account.realized_pnl == Decimal("-5.25")


def test_market_event_requires_aware_time_and_consistent_range() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        market_event(timestamp=NOW.replace(tzinfo=None))

    with pytest.raises(ValueError, match="range"):
        market_event(price="98", low="99", high="101")


@pytest.mark.parametrize(
    "changes",
    [
        {"filled_quantity": "2.01"},
        {"filled_quantity": "0", "average_fill_price": "100"},
        {"side": "LONG"},
        {"status": "FILLED"},
    ],
)
def test_order_rejects_inconsistent_lifecycle_values(
    changes: dict[str, object],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        order(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"symbol": ""},
        {"side": "FLAT", "quantity": "1"},
        {"side": "LONG", "quantity": "0"},
    ],
)
def test_position_rejects_noncanonical_identity_and_flat_state(
    changes: dict[str, object],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        position(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"event_id": ""},
        {"event_type": "entry_fill"},
        {"order_id": ""},
        {"fill_id": ""},
        {"market_sequence": True},
        {"market_sequence": -1},
    ],
)
def test_ledger_event_rejects_malformed_values(
    changes: dict[str, object],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        ledger_event(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"accepted": 1},
        {"reason": "accepted"},
        {"order": object()},
    ],
)
def test_submission_result_rejects_malformed_values(
    changes: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "accepted": True,
        "reason": PaperReason.ACCEPTED,
        "order": order(),
    }
    values.update(changes)

    with pytest.raises((TypeError, ValueError)):
        PaperSubmissionResult(**values)  # type: ignore[arg-type]


def test_reconciliation_reasons_are_deduplicated_sorted_and_unaliased() -> None:
    source = [
        ReconciliationReason.FEE_MISMATCH,
        ReconciliationReason.BALANCE_MISMATCH,
        ReconciliationReason.FEE_MISMATCH,
    ]
    result = ReconciliationResult(
        ReconciliationStatus.MISMATCH,
        source,  # type: ignore[arg-type]
    )
    source.append(ReconciliationReason.OVER_CLOSE)

    assert result.reasons == (
        ReconciliationReason.BALANCE_MISMATCH,
        ReconciliationReason.FEE_MISMATCH,
    )


@pytest.mark.parametrize(
    ("status", "reasons"),
    [
        (
            ReconciliationStatus.MATCHED,
            (ReconciliationReason.BALANCE_MISMATCH,),
        ),
        (
            ReconciliationStatus.MISMATCH,
            (ReconciliationReason.MATCHED,),
        ),
    ],
)
def test_reconciliation_status_and_reasons_must_agree(
    status: ReconciliationStatus,
    reasons: tuple[ReconciliationReason, ...],
) -> None:
    with pytest.raises(ValueError):
        ReconciliationResult(status, reasons)


def test_report_defensively_copies_sequence_inputs() -> None:
    first_fill = fill()
    first_event = ledger_event()
    source_fills = [first_fill]
    source_events = [first_event]

    selected = report(
        fills=source_fills,
        events=source_events,
    )
    source_fills.append(fill(fill_id="fill-2", market_sequence=8))
    source_events.append(
        ledger_event(event_id="event-2", market_sequence=8)
    )

    assert selected.fills == (first_fill,)
    assert selected.events == (first_event,)


@pytest.mark.parametrize(
    "changes",
    [
        {"order": object()},
        {"fills": (object(),)},
        {"position": object()},
        {"account": object()},
        {"events": (object(),)},
    ],
)
def test_report_rejects_wrong_nested_contracts(
    changes: dict[str, object],
) -> None:
    with pytest.raises(TypeError):
        report(**changes)


def test_report_serialization_is_canonical_and_deterministic() -> None:
    first = report()
    equivalent = report(
        order=order(
            quantity=Decimal("2.000"),
            filled_quantity=Decimal("1.000"),
        ),
        fills=(fill(quantity=Decimal("1.000")),),
        position=position(quantity=Decimal("1.000")),
    )

    serialized = first.to_json()

    assert serialized == equivalent.to_json()
    assert serialized == canonical_json(json.loads(serialized))
    assert first.report_id == equivalent.report_id
    assert len(first.report_id) == 64
    assert first.equity == first.account.balance + first.position.unrealized_pnl
    assert "\n" not in serialized
    assert ": " not in serialized
    assert json.loads(serialized) == report_mapping(first)
    assert json.loads(serialized)["order"]["source_timestamp"].endswith("Z")


def test_mapping_helpers_return_fresh_canonical_values() -> None:
    selected = report()
    original_json = selected.to_json()
    mapped = report_mapping(selected)
    mapped["order"]["order_id"] = "mutated"  # type: ignore[index]
    mapped["fills"].clear()  # type: ignore[union-attr]

    assert selected.to_json() == original_json
    assert order_mapping(selected.order)["quantity"] == "2"
    assert fill_mapping(selected.fills[0])["fee"] == "0.05"
    assert position_mapping(selected.position)["unrealized_pnl"] == "1.25"
    assert account_mapping(selected.account)["realized_pnl"] == "-1.25"


def test_checkpoint_digest_is_stable_and_contract_is_frozen() -> None:
    first = checkpoint()
    second = checkpoint(
        {
            "policy_id": "paper-v1",
            "events": [],
            "account": {"version": 3, "balance": "9998.7"},
        }
    )

    assert first == second
    assert len(first.digest) == 64
    assert first.digest == hashlib.sha256(
        f"{first.policy_id}:{first.version}:{first.payload_json}".encode()
    ).hexdigest()


def test_checkpoint_rejects_noncanonical_payload_and_tampering() -> None:
    selected = checkpoint()
    noncanonical = '{"policy_id": "paper-v1", "events": []}'

    with pytest.raises(ValueError, match="canonical"):
        PaperCheckpoint(
            "paper-v1",
            3,
            noncanonical,
            hashlib.sha256(
                f"paper-v1:3:{noncanonical}".encode()
            ).hexdigest(),
        )

    tampered_payload = canonical_json(
        {
            **json.loads(selected.payload_json),
            "latest_sequence": 99,
        }
    )
    with pytest.raises(ValueError, match="digest"):
        PaperCheckpoint(
            selected.policy_id,
            selected.version,
            tampered_payload,
            selected.digest,
        )

    with pytest.raises(ValueError, match="digest"):
        replace(selected, digest="0" * 64)


@pytest.mark.parametrize("payload", [None, [], "payload", 1, True])
def test_checkpoint_requires_a_json_object(payload: object) -> None:
    payload_json = canonical_json(payload)
    digest = hashlib.sha256(
        f"paper-v1:3:{payload_json}".encode()
    ).hexdigest()

    with pytest.raises(ValueError):
        PaperCheckpoint("paper-v1", 3, payload_json, digest)


def test_canonical_json_rejects_non_finite_numbers() -> None:
    with pytest.raises(ValueError):
        canonical_json({"value": float("nan")})

    with pytest.raises(ValueError):
        canonical_json({"value": float("inf")})


class _SecretNumeric:
    def __str__(self) -> str:
        return SECRET


def test_validation_errors_do_not_echo_hostile_payloads() -> None:
    with pytest.raises((TypeError, ValueError)) as numeric_error:
        policy(slippage_bps=_SecretNumeric())

    with pytest.raises(Exception) as checkpoint_error:
        PaperCheckpoint(
            "paper-v1",
            3,
            f'{{"payload":"{SECRET}',
            "0" * 64,
        )

    assert SECRET not in str(numeric_error.value)
    assert SECRET not in str(checkpoint_error.value)
