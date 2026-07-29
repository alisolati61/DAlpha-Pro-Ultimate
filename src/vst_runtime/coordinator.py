"""Lifecycle-controlled, synchronous BingX VST execution coordinator."""

from __future__ import annotations

import hashlib
import threading
import time
from decimal import Decimal
from typing import Any, Callable

from src.core.lifecycle.service import Service
from src.core.services.models import ServiceDefinition
from src.execution_intent.models import ExecutionIntent, IntentStatus

from .errors import (
    VstAmbiguousOutcome,
    VstAuthenticationError,
    VstLifecycleError,
    VstRateLimitError,
    VstSchemaError,
    VstTransportError,
    VstValidationError,
)
from .models import (
    EMPTY_RECONCILIATION,
    KillSwitchState,
    ReconciliationResult,
    ReconciliationState,
    RemoteBalance,
    RemoteFill,
    RemoteOrder,
    RemoteOrderStatus,
    RemotePosition,
    VstCheckpoint,
    VstConfiguration,
    VstExecutionReport,
    VstSubmissionResult,
)
from .reconciliation import VstReconciler
from .transport import VstTransport

VST_SERVICE_ID = "bingx-vst"
Clock = Callable[[], int]
_TERMINAL = {
    RemoteOrderStatus.FILLED,
    RemoteOrderStatus.CANCELED,
    RemoteOrderStatus.REJECTED,
    RemoteOrderStatus.EXPIRED,
}


class BingXVstCoordinator(Service):
    def __init__(
        self,
        configuration: VstConfiguration,
        transport: VstTransport,
        *,
        clock_ms: Clock | None = None,
    ) -> None:
        if not isinstance(configuration, VstConfiguration):
            raise TypeError("configuration must be a VstConfiguration")
        if not isinstance(transport, VstTransport):
            raise TypeError("transport does not satisfy VstTransport")
        self._configuration = configuration
        self._transport = transport
        self._clock = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self._lock = threading.RLock()
        self._initialized = False
        self._running = False
        self._intent_digests: dict[str, str] = {}
        self._client_ids: dict[str, str] = {}
        self._orders: dict[str, RemoteOrder] = {}
        self._fills: dict[str, RemoteFill] = {}
        self._positions: dict[tuple[str, str], RemotePosition] = {}
        self._balance: RemoteBalance | None = None
        self._initial_equity: Decimal | None = None
        self._reconciliation = EMPTY_RECONCILIATION
        self._kill_switch = KillSwitchState()
        self._latest_update_id: str | None = None
        self._version = 0
        self._unknown_count = 0
        self._failures = {"auth": 0, "rate_limit": 0, "schema": 0}

    def definition(self) -> ServiceDefinition:
        return ServiceDefinition(VST_SERVICE_ID, self, ("execution-intent",))

    def initialize(self) -> None:
        with self._lock:
            if self._running:
                raise VstLifecycleError("cannot initialize while running")
            self._transport.initialize()
            self._initialized = True

    def start(self) -> None:
        with self._lock:
            if not self._initialized:
                raise VstLifecycleError("service is not initialized")
            self._transport.start()
            try:
                server_time = self._transport.server_time_ms()
            except Exception as exc:
                raise VstTransportError("server time is unavailable") from exc
            if (
                abs(self._clock() - server_time)
                > self._configuration.maximum_clock_drift_ms
            ):
                self._activate("clock_drift")
                raise VstValidationError("clock drift exceeds policy")
            self._running = True

    def stop(self) -> None:
        with self._lock:
            self._running = False
            self._transport.stop()

    def activate_kill_switch(self, reason_code: str = "explicit_activation") -> None:
        with self._lock:
            self._activate(reason_code)

    def submit_intent(self, intent: ExecutionIntent) -> VstSubmissionResult:
        if not isinstance(intent, ExecutionIntent):
            raise TypeError("intent must be an ExecutionIntent")
        if intent.status is not IntentStatus.READY:
            return VstSubmissionResult(
                intent.intent_id, None, None, False, intent.status.value.lower()
            )
        digest = hashlib.sha256(intent.to_json().encode()).hexdigest()
        with self._lock:
            self._require_running()
            existing_digest = self._intent_digests.get(intent.intent_id)
            if existing_digest is not None:
                if existing_digest != digest:
                    raise VstValidationError("conflicting duplicate intent")
                client_id = self._client_ids[intent.intent_id]
                order = self._orders.get(client_id)
                if order is None or order.status is RemoteOrderStatus.UNKNOWN:
                    order = self._query_after_ambiguity(intent.symbol or "", client_id)
                return VstSubmissionResult(
                    intent.intent_id, client_id, order, True, "idempotent_replay", True
                )
            self._validate_submission(intent)
            client_id = self.client_order_id(intent.intent_id)
            request = self._request(intent, client_id)
            try:
                order = self._transport.submit_order(request)
                self._validate_order(order, intent, client_id)
            except VstAmbiguousOutcome:
                self._intent_digests[intent.intent_id] = digest
                self._client_ids[intent.intent_id] = client_id
                return self._ambiguous_submission(intent, client_id)
            except Exception as exc:
                self._record_failure(exc)
                raise self._safe_transport_error(exc) from exc
            self._intent_digests[intent.intent_id] = digest
            self._client_ids[intent.intent_id] = client_id
            self._orders[client_id] = order
            self._latest_update_id = order.update_id
            self._version += 1
            return VstSubmissionResult(
                intent.intent_id, client_id, order, True, "submitted"
            )

    @staticmethod
    def client_order_id(intent_id: str) -> str:
        value = hashlib.sha256(f"bingx-vst:{intent_id}".encode()).hexdigest()[:24]
        return f"dalphavst-{value}"

    def query_order(self, intent_id: str) -> RemoteOrder | None:
        with self._lock:
            self._require_running()
            client_id = self._client_ids.get(intent_id)
            if client_id is None:
                raise VstValidationError("intent is not accepted")
            local = self._orders.get(client_id)
            symbol = local.symbol if local else ""
            try:
                order = self._transport.query_order(symbol, client_id)
            except Exception as exc:
                self._record_failure(exc)
                raise self._safe_transport_error(exc) from exc
            if order is not None:
                self._orders[client_id] = order
                self._latest_update_id = order.update_id
                self._version += 1
            return order

    def cancel_order(self, intent_id: str) -> RemoteOrder:
        with self._lock:
            self._require_running()
            client_id = self._client_ids.get(intent_id)
            order = self._orders.get(client_id or "")
            if client_id is None or order is None:
                raise VstValidationError("intent is not accepted")
            if order.status in _TERMINAL:
                return order
            try:
                canceled = self._transport.cancel_order(order.symbol, client_id)
            except VstAmbiguousOutcome as exc:
                authoritative = self._transport.query_order(order.symbol, client_id)
                if authoritative is None:
                    self._activate("ambiguous_cancel")
                    raise VstAmbiguousOutcome("cancel outcome is unknown") from exc
                canceled = authoritative
            except Exception as exc:
                self._record_failure(exc)
                raise self._safe_transport_error(exc) from exc
            if canceled.client_order_id != client_id:
                self._activate("cancel_identity_mismatch")
                raise VstSchemaError("cancel response identity mismatch")
            self._orders[client_id] = canceled
            self._latest_update_id = canceled.update_id
            self._version += 1
            return canceled

    def fetch_fills(self, symbol: str | None = None) -> tuple[RemoteFill, ...]:
        with self._lock:
            self._require_running()
            try:
                fills = tuple(self._transport.fetch_fills(symbol))
            except Exception as exc:
                self._record_failure(exc)
                raise self._safe_transport_error(exc) from exc
            self._fills.update((item.fill_id, item) for item in fills)
            self._version += 1
            return fills

    def fetch_positions(self) -> tuple[RemotePosition, ...]:
        with self._lock:
            self._require_running()
            try:
                positions = tuple(self._transport.fetch_positions())
            except Exception as exc:
                self._record_failure(exc)
                raise self._safe_transport_error(exc) from exc
            self._positions = {(item.symbol, item.side): item for item in positions}
            self._check_stale([item.updated_at_ms for item in positions])
            self._version += 1
            return positions

    def fetch_balance(self) -> RemoteBalance:
        with self._lock:
            self._require_running()
            try:
                balance = self._transport.fetch_balance()
            except Exception as exc:
                self._record_failure(exc)
                raise self._safe_transport_error(exc) from exc
            self._balance = balance
            if self._initial_equity is None:
                self._initial_equity = balance.equity
            elif (
                self._initial_equity - balance.equity
                >= self._configuration.maximum_session_loss
            ):
                self._activate("maximum_session_loss")
            self._check_stale([balance.updated_at_ms])
            self._version += 1
            return balance

    def reconcile(self) -> ReconciliationResult:
        with self._lock:
            self._require_running()
            checkpoint = self.export_checkpoint()
            try:
                orders = tuple(self._transport.fetch_orders())
                fills = tuple(self._transport.fetch_fills())
                positions = tuple(self._transport.fetch_positions())
                balance = self._transport.fetch_balance()
            except Exception:
                result = ReconciliationResult(
                    ReconciliationState.UNKNOWN,
                    ("remote_state_unavailable",),
                    ("retry_read_only_reconciliation",),
                )
            else:
                result = VstReconciler.reconcile(
                    checkpoint,
                    orders=orders,
                    fills=fills,
                    positions=positions,
                    balance=balance,
                )
            self._reconciliation = result
            if result.state is ReconciliationState.MISMATCH:
                self._activate("reconciliation_mismatch")
            elif result.state is ReconciliationState.UNKNOWN:
                self._unknown_count += 1
                if self._unknown_count >= self._configuration.unknown_limit:
                    self._activate("reconciliation_unknown")
            else:
                self._unknown_count = 0
            self._version += 1
            return result

    def export_checkpoint(self) -> VstCheckpoint:
        with self._lock:
            return VstCheckpoint(
                policy_id=self._configuration.policy_id,
                accepted_intent_ids=tuple(sorted(self._intent_digests)),
                client_order_ids=tuple(sorted(self._client_ids.items())),
                intent_digests=tuple(sorted(self._intent_digests.items())),
                orders=tuple(
                    sorted(self._orders.values(), key=lambda item: item.client_order_id)
                ),
                fills=tuple(
                    sorted(self._fills.values(), key=lambda item: item.fill_id)
                ),
                positions=tuple(
                    sorted(
                        self._positions.values(),
                        key=lambda item: (item.symbol, item.side),
                    )
                ),
                balance=self._balance,
                reconciliation=self._reconciliation,
                kill_switch=self._kill_switch,
                latest_update_id=self._latest_update_id,
                version=self._version,
            )

    def restore_checkpoint(self, checkpoint: VstCheckpoint) -> None:
        if not isinstance(checkpoint, VstCheckpoint):
            raise TypeError("checkpoint must be a VstCheckpoint")
        validated = VstCheckpoint(
            policy_id=checkpoint.policy_id,
            accepted_intent_ids=checkpoint.accepted_intent_ids,
            client_order_ids=checkpoint.client_order_ids,
            intent_digests=checkpoint.intent_digests,
            orders=checkpoint.orders,
            fills=checkpoint.fills,
            positions=checkpoint.positions,
            balance=checkpoint.balance,
            reconciliation=checkpoint.reconciliation,
            kill_switch=checkpoint.kill_switch,
            latest_update_id=checkpoint.latest_update_id,
            version=checkpoint.version,
            digest=checkpoint.digest,
        )
        if validated.policy_id != self._configuration.policy_id:
            raise VstValidationError("checkpoint policy does not match")
        client_ids = dict(validated.client_order_ids)
        digests = dict(validated.intent_digests)
        if set(validated.accepted_intent_ids) != set(client_ids) or set(
            client_ids
        ) != set(digests):
            raise VstValidationError("checkpoint intent indexes are inconsistent")
        orders = {item.client_order_id: item for item in validated.orders}
        if len(orders) != len(validated.orders):
            raise VstValidationError("checkpoint contains duplicate orders")
        with self._lock:
            self._client_ids = client_ids
            self._intent_digests = digests
            self._orders = orders
            self._fills = {item.fill_id: item for item in validated.fills}
            self._positions = {
                (item.symbol, item.side): item for item in validated.positions
            }
            self._balance = validated.balance
            self._reconciliation = validated.reconciliation
            self._kill_switch = validated.kill_switch
            self._latest_update_id = validated.latest_update_id
            self._version = validated.version

    def execution_report(self) -> VstExecutionReport:
        return VstExecutionReport(self.export_checkpoint())

    @property
    def kill_switch(self) -> KillSwitchState:
        return self._kill_switch

    def _validate_submission(self, intent: ExecutionIntent) -> None:
        if self._kill_switch.active:
            raise VstValidationError("kill switch blocks submission")
        if intent.symbol not in self._configuration.symbols:
            raise VstValidationError("symbol is not allowlisted")
        if intent.exchange is None or intent.exchange.lower() != "bingx":
            raise VstValidationError("intent exchange is unsupported")
        if (
            intent.entry is None
            or intent.stop_loss is None
            or intent.take_profit is None
        ):
            raise VstValidationError("unprotected entry is forbidden")
        if not self._transport.supports_protected_entry:
            raise VstValidationError("safe protected entry is unsupported")
        notional = intent.entry.quantity * intent.entry.price
        if notional > self._configuration.maximum_order_notional:
            self._activate("maximum_order_notional")
            raise VstValidationError("maximum order notional exceeded")
        exposure = sum(
            (item.quantity * item.entry_price for item in self._positions.values()),
            Decimal(0),
        )
        maximum_exposure = self._configuration.maximum_exposure
        if maximum_exposure is not None and exposure + notional > maximum_exposure:
            self._activate("maximum_exposure")
            raise VstValidationError("maximum exposure exceeded")
        open_positions = sum(item.quantity > 0 for item in self._positions.values())
        if open_positions >= self._configuration.maximum_open_positions:
            self._activate("maximum_open_positions")
            raise VstValidationError("maximum open positions exceeded")

    @staticmethod
    def _request(intent: ExecutionIntent, client_id: str) -> dict[str, Any]:
        assert (
            intent.entry and intent.stop_loss and intent.take_profit and intent.symbol
        )
        return {
            "clientOrderId": client_id,
            "symbol": intent.symbol,
            "side": intent.entry.side.value,
            "positionSide": "LONG" if intent.entry.side.value == "BUY" else "SHORT",
            "type": intent.entry.order_type.value,
            "quantity": intent.entry.quantity,
            "price": intent.entry.price,
            "timeInForce": intent.entry.time_in_force.value,
            "stopLoss": intent.stop_loss.price,
            "takeProfit": intent.take_profit.price,
        }

    @staticmethod
    def _validate_order(
        order: RemoteOrder, intent: ExecutionIntent, client_id: str
    ) -> None:
        assert intent.entry and intent.symbol
        if (
            order.client_order_id != client_id
            or order.symbol != intent.symbol
            or order.original_quantity != intent.entry.quantity
            or order.price != intent.entry.price
        ):
            raise VstSchemaError("submit response does not match intent")

    def _ambiguous_submission(
        self, intent: ExecutionIntent, client_id: str
    ) -> VstSubmissionResult:
        try:
            order = self._query_after_ambiguity(intent.symbol or "", client_id)
        except VstAmbiguousOutcome:
            order = RemoteOrder(
                client_id,
                "unknown",
                intent.symbol or "unknown",
                intent.entry.side.value if intent.entry else "UNKNOWN",
                intent.entry.order_type.value if intent.entry else "UNKNOWN",
                RemoteOrderStatus.UNKNOWN,
                intent.entry.quantity if intent.entry else Decimal(0),
                Decimal(0),
                Decimal(0),
                intent.entry.price if intent.entry else Decimal(0),
                "unknown",
                self._clock(),
            )
            self._orders[client_id] = order
            self._activate("ambiguous_submit")
            self._version += 1
            return VstSubmissionResult(
                intent.intent_id, client_id, order, False, "ambiguous_submit"
            )
        self._orders[client_id] = order
        self._version += 1
        return VstSubmissionResult(
            intent.intent_id, client_id, order, True, "recovered_after_timeout"
        )

    def _query_after_ambiguity(self, symbol: str, client_id: str) -> RemoteOrder:
        try:
            order = self._transport.query_order(symbol, client_id)
        except Exception as exc:
            raise VstAmbiguousOutcome("authoritative order query failed") from exc
        if order is None:
            raise VstAmbiguousOutcome("authoritative order state is unknown")
        if order.client_order_id != client_id:
            raise VstSchemaError("authoritative order identity mismatch")
        return order

    def _activate(self, reason: str) -> None:
        reasons = tuple(sorted(set(self._kill_switch.reason_codes + (reason,))))
        self._kill_switch = KillSwitchState(True, reasons)

    def _require_running(self) -> None:
        if not self._running:
            raise VstLifecycleError("service is not running")

    def _check_stale(self, timestamps: list[int]) -> None:
        if timestamps and any(
            self._clock() - value > self._configuration.stale_after_ms
            for value in timestamps
        ):
            self._activate("stale_remote_data")

    def _record_failure(self, error: Exception) -> None:
        key = (
            "auth"
            if isinstance(error, VstAuthenticationError)
            else (
                "rate_limit"
                if isinstance(error, VstRateLimitError)
                else "schema" if isinstance(error, VstSchemaError) else None
            )
        )
        if key is not None:
            self._failures[key] += 1
            if self._failures[key] >= self._configuration.failure_limit:
                self._activate(f"repeated_{key}_failure")

    @staticmethod
    def _safe_transport_error(error: Exception) -> VstTransportError:
        if isinstance(error, VstTransportError):
            return error
        return VstTransportError("VST transport operation failed")


__all__ = ("BingXVstCoordinator", "VST_SERVICE_ID")
