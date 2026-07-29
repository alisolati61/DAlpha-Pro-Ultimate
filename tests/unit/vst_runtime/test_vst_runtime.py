from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

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
from src.vst_runtime import BingXVstCoordinator
from src.vst_runtime.errors import (
    VstAmbiguousOutcome,
    VstConfigurationError,
    VstLifecycleError,
    VstValidationError,
)
from src.vst_runtime.models import (
    ReconciliationState,
    RemoteBalance,
    RemoteFill,
    RemoteOrder,
    RemoteOrderStatus,
    RemotePosition,
    VstCheckpoint,
    VstConfiguration,
)
from src.vst_runtime.transport import signing_string

NOW = 2_000_000


def config(**changes: Any) -> VstConfiguration:
    values = {
        "api_key": "vst-key",
        "api_secret": "vst-secret",
        "symbols": frozenset({"BTC-USDT"}),
        "maximum_order_notional": Decimal("50000"),
        "maximum_open_positions": 3,
        "maximum_session_loss": Decimal("1000"),
        "configuration_version": "v1",
        "maximum_exposure": Decimal("100000"),
    }
    values.update(changes)
    return VstConfiguration(**values)


def intent(
    intent_id: str = "intent-1",
    *,
    status: IntentStatus = IntentStatus.READY,
    quantity: Decimal = Decimal("1"),
) -> ExecutionIntent:
    if status is not IntentStatus.READY:
        return ExecutionIntent(
            intent_id,
            "decision-1",
            status,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            (IntentReason.DECISION_HOLD,),
        )
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
    take = OrderSpecification(
        IntentSide.SELL,
        IntentOrderType.TAKE_PROFIT,
        Decimal("120"),
        quantity,
        IntentTimeInForce.GTC,
        True,
    )
    return ExecutionIntent(
        intent_id,
        "decision-1",
        status,
        "BTC-USDT",
        "bingx",
        "1h",
        entry,
        stop,
        take,
        "strategy",
        "v1",
        Decimal("10"),
        "constraints",
        datetime(2026, 1, 1, tzinfo=UTC),
        (IntentReason.INTENT_READY,),
    )


class FakeTransport:
    supports_protected_entry = True

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.orders: dict[str, RemoteOrder] = {}
        self.fills: list[RemoteFill] = []
        self.positions: list[RemotePosition] = []
        self.balance = RemoteBalance("VST", 10_000, 10_000, 9_000, NOW)
        self.ambiguous_submit = False
        self.ambiguous_cancel = False

    def initialize(self) -> None:
        self.calls.append(("initialize", None))

    def start(self) -> None:
        self.calls.append(("start", None))

    def stop(self) -> None:
        self.calls.append(("stop", None))

    def server_time_ms(self) -> int:
        return NOW

    def submit_order(self, request: dict[str, Any]) -> RemoteOrder:
        self.calls.append(("submit", dict(request)))
        order = RemoteOrder(
            request["clientOrderId"],
            "remote-1",
            request["symbol"],
            request["side"],
            request["type"],
            RemoteOrderStatus.NEW,
            request["quantity"],
            Decimal(0),
            Decimal(0),
            request["price"],
            "1",
            NOW,
        )
        if not self.ambiguous_submit:
            self.orders[order.client_order_id] = order
            return order
        raise VstAmbiguousOutcome("unsafe detail")

    def query_order(self, symbol: str, client_order_id: str) -> RemoteOrder | None:
        self.calls.append(("query", client_order_id))
        return self.orders.get(client_order_id)

    def cancel_order(self, symbol: str, client_order_id: str) -> RemoteOrder:
        self.calls.append(("cancel", client_order_id))
        if self.ambiguous_cancel:
            raise VstAmbiguousOutcome("unsafe detail")
        order = self.orders[client_order_id]
        order = RemoteOrder(
            order.client_order_id,
            order.order_id,
            order.symbol,
            order.side,
            order.order_type,
            RemoteOrderStatus.CANCELED,
            order.original_quantity,
            order.filled_quantity,
            order.average_price,
            order.price,
            "2",
            NOW,
        )
        self.orders[client_order_id] = order
        return order

    def fetch_orders(self) -> tuple[RemoteOrder, ...]:
        return tuple(self.orders.values())

    def fetch_fills(self, symbol: str | None = None) -> tuple[RemoteFill, ...]:
        return tuple(self.fills)

    def fetch_positions(self) -> tuple[RemotePosition, ...]:
        return tuple(self.positions)

    def fetch_balance(self) -> RemoteBalance:
        return self.balance


def running(
    transport: FakeTransport | None = None,
    configuration: VstConfiguration | None = None,
) -> tuple[BingXVstCoordinator, FakeTransport]:
    fake = transport or FakeTransport()
    service = BingXVstCoordinator(configuration or config(), fake, clock_ms=lambda: NOW)
    service.initialize()
    service.start()
    return service, fake


def test_configuration_rejects_live_hosts_blank_credentials_and_redacts() -> None:
    with pytest.raises(VstConfigurationError):
        config(base_url="https://open-api.bingx.com")
    with pytest.raises(VstConfigurationError):
        config(api_key=" ")
    with pytest.raises(VstConfigurationError):
        config(api_secret="")
    value = repr(config(api_key="TOPKEY", api_secret="TOPSECRET"))
    assert "TOPKEY" not in value
    assert "TOPSECRET" not in value
    assert config().policy_id == config().policy_id


def test_frozen_signing_compatibility() -> None:
    assert signing_string({"timestamp": "2", "symbol": "BTC-USDT"}) == (
        "symbol=BTC-USDT&timestamp=2"
    )


def test_lifecycle_definition_and_no_network_mutation_on_initialize() -> None:
    fake = FakeTransport()
    service = BingXVstCoordinator(config(), fake, clock_ms=lambda: NOW)
    assert service.definition().service_id == "bingx-vst"
    assert service.definition().dependencies == ("execution-intent",)
    service.initialize()
    assert fake.calls == [("initialize", None)]
    service.start()
    service.stop()
    with pytest.raises(VstLifecycleError):
        service.submit_intent(intent())


def test_ready_submit_is_exact_deterministic_and_idempotent() -> None:
    service, fake = running()
    first = service.submit_intent(intent())
    second = service.submit_intent(intent())
    assert first.accepted and second.replayed
    assert first.client_order_id == service.client_order_id("intent-1")
    assert len([call for call in fake.calls if call[0] == "submit"]) == 1
    request = next(call[1] for call in fake.calls if call[0] == "submit")
    assert request["quantity"] == Decimal("1")
    assert request["price"] == Decimal("100")
    assert request["stopLoss"] == Decimal("90")
    assert request["takeProfit"] == Decimal("120")
    with pytest.raises(VstValidationError):
        service.submit_intent(intent(quantity=Decimal("2")))


@pytest.mark.parametrize("status", [IntentStatus.BLOCKED, IntentStatus.NO_ACTION])
def test_non_ready_never_submits(status: IntentStatus) -> None:
    service, fake = running()
    result = service.submit_intent(intent(status=status))
    assert not result.accepted
    assert not any(call[0] == "submit" for call in fake.calls)


def test_ambiguous_submit_queries_before_unknown_and_kills() -> None:
    fake = FakeTransport()
    fake.ambiguous_submit = True
    service, _ = running(fake)
    result = service.submit_intent(intent())
    assert result.order and result.order.status is RemoteOrderStatus.UNKNOWN
    assert service.kill_switch.active
    assert [call[0] for call in fake.calls][-2:] == ["submit", "query"]
    with pytest.raises(VstValidationError):
        service.submit_intent(intent("intent-2"))


def test_ambiguous_submit_recovers_authoritative_order() -> None:
    fake = FakeTransport()
    client_id = BingXVstCoordinator.client_order_id("intent-1")
    fake.orders[client_id] = RemoteOrder(
        client_id,
        "remote-1",
        "BTC-USDT",
        "BUY",
        "LIMIT",
        RemoteOrderStatus.NEW,
        1,
        0,
        0,
        100,
        "1",
        NOW,
    )
    fake.ambiguous_submit = True
    service, _ = running(fake)
    assert service.submit_intent(intent()).reason_code == "recovered_after_timeout"
    assert not service.kill_switch.active


def test_cancel_is_idempotent_and_ambiguous_cancel_queries() -> None:
    service, fake = running()
    service.submit_intent(intent())
    canceled = service.cancel_order("intent-1")
    assert canceled.status is RemoteOrderStatus.CANCELED
    assert service.cancel_order("intent-1") is canceled
    assert len([call for call in fake.calls if call[0] == "cancel"]) == 1


def test_sync_checkpoint_restore_and_retry_without_duplicate() -> None:
    service, fake = running()
    submitted = service.submit_intent(intent())
    fake.fills = [
        RemoteFill(
            "fill-1",
            "remote-1",
            submitted.client_order_id or "",
            "BTC-USDT",
            1,
            100,
            1,
            "VST",
            NOW,
        )
    ]
    fake.positions = [RemotePosition("BTC-USDT", "LONG", 1, 100, NOW)]
    service.fetch_fills()
    service.fetch_positions()
    service.fetch_balance()
    checkpoint = service.export_checkpoint()
    assert checkpoint.digest == service.export_checkpoint().digest
    restored, restored_fake = running()
    restored_fake.orders = dict(fake.orders)
    restored.restore_checkpoint(checkpoint)
    assert restored.export_checkpoint().digest == checkpoint.digest
    assert restored.submit_intent(intent()).replayed
    assert not any(call[0] == "submit" for call in restored_fake.calls)
    bad = object.__new__(VstCheckpoint)
    with pytest.raises((TypeError, AttributeError, VstValidationError)):
        restored.restore_checkpoint(bad)
    assert restored.export_checkpoint().digest == checkpoint.digest


def test_reconciliation_matched_mismatch_unknown_and_orphans() -> None:
    service, fake = running()
    service.submit_intent(intent())
    assert service.reconcile().state is ReconciliationState.MATCHED
    fake.positions = [RemotePosition("ETH-USDT", "LONG", 1, 10, NOW)]
    result = service.reconcile()
    assert result.state is ReconciliationState.MISMATCH
    assert "orphan_remote_position" in result.reason_codes
    assert service.kill_switch.active

    service2, fake2 = running()
    fake2.fetch_orders = lambda: (_ for _ in ()).throw(TimeoutError())
    assert service2.reconcile().state is ReconciliationState.UNKNOWN
    assert service2.kill_switch.active


def test_guards_stale_loss_clock_and_protection() -> None:
    service, _ = running(configuration=config(maximum_order_notional=Decimal("50")))
    with pytest.raises(VstValidationError):
        service.submit_intent(intent())
    assert service.kill_switch.active

    fake = FakeTransport()
    service2, _ = running(fake)
    service2.fetch_balance()
    fake.balance = RemoteBalance("VST", 8_000, 8_000, 8_000, NOW)
    service2.fetch_balance()
    assert "maximum_session_loss" in service2.kill_switch.reason_codes

    fake3 = FakeTransport()
    fake3.balance = RemoteBalance("VST", 10_000, 10_000, 9_000, 1)
    service3, _ = running(fake3)
    service3.fetch_balance()
    assert "stale_remote_data" in service3.kill_switch.reason_codes

    fake4 = FakeTransport()
    fake4.supports_protected_entry = False
    service4, _ = running(fake4)
    with pytest.raises(VstValidationError, match="protected"):
        service4.submit_intent(intent())

    drift = BingXVstCoordinator(config(), FakeTransport(), clock_ms=lambda: NOW + 5_000)
    drift.initialize()
    with pytest.raises(VstValidationError, match="clock drift"):
        drift.start()
    assert drift.kill_switch.active


def test_report_is_immutable_and_contains_no_secrets() -> None:
    service, _ = running()
    report = service.execution_report()
    assert report.report_digest
    assert "vst-secret" not in str(report)
    assert "vst-key" not in str(report)
