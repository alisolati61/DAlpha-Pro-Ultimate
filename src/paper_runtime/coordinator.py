"""Synchronous deterministic paper execution with explicit market advancement."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Decimal, localcontext
from threading import RLock

from src.core.lifecycle.service import Service
from src.core.services.models import ServiceDefinition
from src.data.service import MARKET_DATA_SERVICE_ID
from src.execution.order_tracker import OrderStatus, OrderTracker
from src.execution.slippage import SlippageCalculator
from src.execution_intent.models import (
    ExecutionIntent,
    IntentOrderType,
    IntentSide,
    IntentStatus,
)
from src.execution_intent.service import EXECUTION_INTENT_SERVICE_ID
from src.paper_runtime.models import (
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
    PaperProtectionKind,
    PaperProtectionSnapshot,
    PaperReason,
    PaperSubmissionResult,
    account_mapping,
    canonical_json,
    fill_mapping,
    market_mapping,
    order_mapping,
    position_mapping,
    protection_mapping,
)

PAPER_EXECUTION_SERVICE_ID = "paper-execution"


class PaperRuntimeError(Exception):
    def __init__(self) -> None:
        super().__init__("Paper execution operation failed.")


@dataclass(slots=True)
class _OrderRecord:
    order_id: str
    intent_id: str
    symbol: str
    exchange: str
    timeframe: str
    constraints_id: str
    side: str
    quantity: Decimal
    limit_price: Decimal
    stop_price: Decimal
    target_price: Decimal
    filled_quantity: Decimal
    fill_notional: Decimal
    fees: Decimal
    status: OrderStatus
    source_timestamp: datetime
    source_sequence: int
    eligible_after_sequence: int
    eligible_after_timestamp: datetime
    last_entry_sequence: int | None = None

    @property
    def remaining_quantity(self) -> Decimal:
        return self.quantity - self.filled_quantity


@dataclass(slots=True)
class _PositionRecord:
    symbol: str
    side: str
    quantity: Decimal
    average_entry_price: Decimal
    realized_pnl: Decimal
    mark_price: Decimal


@dataclass(slots=True)
class _ProtectionRecord:
    protection_id: str
    parent_order_id: str
    sibling_id: str
    intent_id: str
    symbol: str
    side: str
    kind: PaperProtectionKind
    trigger_price: Decimal
    active_quantity: Decimal
    filled_quantity: Decimal
    fees: Decimal
    status: OrderStatus


CommitHook = Callable[[str], None]
_PrivateState = tuple[
    dict[str, _OrderRecord],
    dict[str, str],
    list[PaperFill],
    list[PaperLedgerEvent],
    dict[str, _PositionRecord],
    dict[str, _ProtectionRecord],
    PaperAccountSnapshot,
    PaperMarketEvent | None,
]


class PaperExecutionCoordinator(Service):
    """Own an isolated in-memory paper ledger; never call execution or exchange."""

    def __init__(
        self,
        policy: PaperExecutionPolicy,
        starting_account: PaperAccountSnapshot,
        *,
        commit_hook: CommitHook | None = None,
    ) -> None:
        self.policy = policy
        self._initial_account = starting_account
        self._account = starting_account
        self._commit_hook = commit_hook
        self._orders: dict[str, _OrderRecord] = {}
        self._intent_fingerprints: dict[str, str] = {}
        self._fills: list[PaperFill] = []
        self._events: list[PaperLedgerEvent] = []
        self._positions: dict[str, _PositionRecord] = {}
        self._protections: dict[str, _ProtectionRecord] = {}
        self._latest_market: PaperMarketEvent | None = None
        self._running = False
        self._lock = RLock()

    def initialize(self) -> None:
        if not isinstance(self.policy, PaperExecutionPolicy):
            raise TypeError("paper policy is invalid")
        if not isinstance(self._initial_account, PaperAccountSnapshot):
            raise TypeError("starting account is invalid")
        if any(
            value != 0
            for value in (
                self._initial_account.reserved_margin,
                self._initial_account.used_margin,
                self._initial_account.fees_paid,
                self._initial_account.realized_pnl,
                self._initial_account.exposure,
            )
        ):
            raise ValueError("starting account must not contain runtime state")
        if (
            self._initial_account.balance
            != self._initial_account.starting_balance
            or self._initial_account.available_balance
            != self._initial_account.balance
            or self._initial_account.version != 0
        ):
            raise ValueError("starting account is inconsistent")
        if self._commit_hook is not None and not callable(self._commit_hook):
            raise TypeError("commit_hook is invalid")

    def start(self) -> None:
        with self._lock:
            self._running = True

    def stop(self) -> None:
        with self._lock:
            self._running = False
            self._clear()

    def definition(self) -> ServiceDefinition:
        return ServiceDefinition(
            PAPER_EXECUTION_SERVICE_ID,
            self,
            (EXECUTION_INTENT_SERVICE_ID, MARKET_DATA_SERVICE_ID),
        )

    def submit_intent(
        self,
        intent: ExecutionIntent,
        *,
        source_sequence: int,
    ) -> PaperSubmissionResult:
        """Validate and idempotently register one READY canonical intent."""
        if not isinstance(intent, ExecutionIntent):
            raise TypeError("intent must be an ExecutionIntent")
        with self._lock:
            self._require_running()
            if intent.status is not IntentStatus.READY:
                return PaperSubmissionResult(
                    False, PaperReason.INTENT_NOT_READY, None
                )
            prepared = self._prepare_order(intent, source_sequence)
            fingerprint = hashlib.sha256(
                f"{intent.to_json()}:{source_sequence}".encode()
            ).hexdigest()
            previous = self._intent_fingerprints.get(intent.intent_id)
            if previous is not None:
                if previous != fingerprint:
                    return PaperSubmissionResult(
                        False, PaperReason.DUPLICATE_CONFLICT, None
                    )
                order = next(
                    item
                    for item in self._orders.values()
                    if item.intent_id == intent.intent_id
                )
                return PaperSubmissionResult(
                    True,
                    PaperReason.EXISTING_SUBMISSION,
                    self._order_snapshot(order),
                )
            if any(
                item.symbol == prepared.symbol
                for item in self._orders.values()
            ):
                return PaperSubmissionResult(
                    False, PaperReason.INVALID_INTENT, None
                )
            required_margin = (
                self._divide(
                    prepared.quantity * prepared.limit_price,
                    self.policy.leverage,
                )
            )
            if required_margin > self._account.available_balance:
                return PaperSubmissionResult(
                    False, PaperReason.INSUFFICIENT_BALANCE, None
                )
            before = self._private_state()
            try:
                self._orders[prepared.order_id] = prepared
                for protection in self._prepare_protections(prepared):
                    self._protections[protection.protection_id] = protection
                self._intent_fingerprints[intent.intent_id] = fingerprint
                self._account = self._account_after(
                    reserved_delta=required_margin
                )
                self._publish(
                    PaperEventType.ORDER_CREATED,
                    prepared.order_id,
                    None,
                    None,
                    {
                        "intent_id": prepared.intent_id,
                        "quantity": str(prepared.quantity),
                        "status": OrderStatus.CREATED.value,
                    },
                )
                self._publish(
                    PaperEventType.ORDER_ACCEPTED,
                    prepared.order_id,
                    None,
                    None,
                    {
                        "limit_price": str(prepared.limit_price),
                        "quantity": str(prepared.quantity),
                        "reserved_margin": str(required_margin),
                        "side": prepared.side,
                        "status": OrderStatus.SENT.value,
                    },
                )
                self._hook("order_registration")
            except Exception:
                self._restore_private(before)
                raise PaperRuntimeError from None
            return PaperSubmissionResult(
                True, PaperReason.ACCEPTED, self._order_snapshot(prepared)
            )

    def advance_market(
        self,
        event: PaperMarketEvent,
    ) -> tuple[PaperLedgerEvent, ...]:
        """Advance only on a strictly newer explicit event.

        Entry eligibility is strictly after both the intent source and the
        market cursor observed at submission. A range that touches both
        protections is resolved stop-first; stops use the worse of their
        threshold and the explicit event price.
        """
        if not isinstance(event, PaperMarketEvent):
            raise TypeError("event must be a PaperMarketEvent")
        with self._lock:
            self._require_running()
            if (
                self._latest_market is not None
                and (
                    event.sequence <= self._latest_market.sequence
                    or event.timestamp <= self._latest_market.timestamp
                )
            ):
                raise PaperRuntimeError
            before = self._private_state()
            event_start = len(self._events)
            try:
                self._publish(
                    PaperEventType.MARKET_ACCEPTED,
                    "paper-market",
                    None,
                    event.sequence,
                    market_mapping(event),
                )
                remaining_liquidity = event.available_quantity
                for order in tuple(self._orders.values()):
                    if (
                        order.symbol != event.symbol
                        or order.exchange != event.exchange
                        or order.timeframe != event.timeframe
                    ):
                        continue
                    if order.status in {
                        OrderStatus.SENT,
                        OrderStatus.PARTIALLY_FILLED,
                    } and order.filled_quantity < order.quantity:
                        remaining_liquidity = self._maybe_fill_entry(
                            order, event, remaining_liquidity
                        )
                    position = self._positions.get(order.symbol)
                    if (
                        position is not None
                        and position.quantity > 0
                        and order.last_entry_sequence is not None
                        and event.sequence > order.last_entry_sequence
                    ):
                        remaining_liquidity = self._maybe_fill_protection(
                            order, position, event, remaining_liquidity
                        )
                self._mark_positions(event)
                self._latest_market = event
                self._hook("market_commit")
            except Exception:
                self._restore_private(before)
                raise PaperRuntimeError from None
            return tuple(self._events[event_start:])

    def cancel(self, order_id: str) -> PaperSubmissionResult:
        """Cancel only the local unfilled remainder and release its margin."""
        with self._lock:
            self._require_running()
            order = self._orders.get(order_id)
            if order is None:
                return PaperSubmissionResult(
                    False, PaperReason.INVALID_INTENT, None
                )
            if order.status.terminal:
                return PaperSubmissionResult(
                    False, PaperReason.TERMINAL_ORDER, self._order_snapshot(order)
                )
            before = self._private_state()
            try:
                release = (
                    self._divide(
                        order.remaining_quantity * order.limit_price,
                        self.policy.leverage,
                    )
                )
                if not OrderTracker.can_transition(
                    order.status, OrderStatus.CANCELLED
                ):
                    raise ValueError
                order.status = OrderStatus.CANCELLED
                self._account = self._account_after(reserved_delta=-release)
                self._publish(
                    PaperEventType.ORDER_CANCELED,
                    order.order_id,
                    None,
                    None,
                    {
                        "released_margin": str(release),
                        "remaining_quantity": str(order.remaining_quantity),
                        "status": order.status.value,
                    },
                )
                if order.filled_quantity == 0:
                    for protection in self._protections.values():
                        if protection.parent_order_id != order.order_id:
                            continue
                        if not OrderTracker.can_transition(
                            protection.status, OrderStatus.CANCELLED
                        ):
                            raise ValueError
                        protection.status = OrderStatus.CANCELLED
                        self._publish(
                            PaperEventType.PROTECTION_CANCELED,
                            protection.protection_id,
                            None,
                            None,
                            {
                                "active_quantity": "0",
                                "parent_order_id": order.order_id,
                                "reason": "entry_canceled",
                                "status": protection.status.value,
                            },
                        )
                self._hook("cancel")
            except Exception:
                self._restore_private(before)
                raise PaperRuntimeError from None
            return PaperSubmissionResult(
                True, PaperReason.CANCELED, self._order_snapshot(order)
            )

    def order(self, order_id: str) -> PaperOrderSnapshot:
        with self._lock:
            return self._order_snapshot(self._orders[order_id])

    def position(self, symbol: str) -> PaperPositionSnapshot:
        with self._lock:
            position = self._positions.get(symbol)
            return (
                self._flat_position(symbol)
                if position is None
                else self._position_snapshot(position)
            )

    @property
    def account(self) -> PaperAccountSnapshot:
        with self._lock:
            return self._account

    @property
    def fills(self) -> tuple[PaperFill, ...]:
        with self._lock:
            return tuple(self._fills)

    @property
    def events(self) -> tuple[PaperLedgerEvent, ...]:
        with self._lock:
            return tuple(self._events)

    @property
    def protections(self) -> tuple[PaperProtectionSnapshot, ...]:
        with self._lock:
            return tuple(
                self._protection_snapshot(item)
                for item in self._protections.values()
            )

    def report(self, order_id: str) -> PaperExecutionReport:
        with self._lock:
            order = self._orders[order_id]
            return PaperExecutionReport(
                order=self._order_snapshot(order),
                fills=tuple(
                    fill
                    for fill in self._fills
                    if fill.order_id == order_id
                    or fill.parent_order_id == order_id
                ),
                position=self.position(order.symbol),
                account=self._account,
                events=tuple(self._events),
                protections=tuple(
                    self._protection_snapshot(item)
                    for item in self._protections.values()
                    if item.parent_order_id == order_id
                ),
            )

    def export_checkpoint(self) -> PaperCheckpoint:
        """Return a canonical integrity-checked in-memory state snapshot."""
        with self._lock:
            payload = self._checkpoint_mapping()
            serialized = canonical_json(payload)
            version = self._account.version
            return PaperCheckpoint(
                self.policy.policy_id,
                version,
                serialized,
                hashlib.sha256(
                    f"{self.policy.policy_id}:{version}:{serialized}".encode()
                ).hexdigest(),
            )

    def restore_checkpoint(self, checkpoint: PaperCheckpoint) -> None:
        """Validate a complete checkpoint before atomically replacing state."""
        if not isinstance(checkpoint, PaperCheckpoint):
            raise TypeError("checkpoint must be a PaperCheckpoint")
        if checkpoint.policy_id != self.policy.policy_id:
            raise PaperRuntimeError
        parsed = json.loads(checkpoint.payload_json)
        if (
            not isinstance(parsed, dict)
            or not isinstance(parsed.get("account"), dict)
            or int(str(parsed["account"].get("version"))) != checkpoint.version
        ):
            raise PaperRuntimeError
        prepared = self._state_from_mapping(parsed)
        with self._lock:
            self._require_running()
            before = self._private_state()
            try:
                self._restore_private(prepared)
                self._hook("checkpoint_restore")
            except Exception:
                self._restore_private(before)
                raise PaperRuntimeError from None

    def _prepare_order(
        self, intent: ExecutionIntent, source_sequence: int
    ) -> _OrderRecord:
        if (
            not isinstance(source_sequence, int)
            or isinstance(source_sequence, bool)
            or source_sequence < 0
            or intent.entry is None
            or intent.stop_loss is None
            or intent.take_profit is None
            or intent.symbol is None
            or intent.exchange is None
            or intent.timeframe is None
            or intent.constraints_id is None
            or intent.source_timestamp is None
        ):
            raise PaperRuntimeError
        if (
            self.policy.constraints_id is not None
            and intent.constraints_id != self.policy.constraints_id
        ):
            raise PaperRuntimeError
        if (
            intent.entry.order_type is not IntentOrderType.LIMIT
            or intent.entry.reduce_only
            or intent.stop_loss.order_type is not IntentOrderType.STOP
            or intent.take_profit.order_type
            is not IntentOrderType.TAKE_PROFIT
        ):
            raise PaperRuntimeError
        side = intent.entry.side.value
        opposite = "SELL" if side == "BUY" else "BUY"
        if (
            intent.stop_loss.quantity != intent.entry.quantity
            or intent.take_profit.quantity != intent.entry.quantity
            or not intent.stop_loss.reduce_only
            or not intent.take_profit.reduce_only
            or intent.stop_loss.side.value != opposite
            or intent.take_profit.side.value != opposite
        ):
            raise PaperRuntimeError
        if side == "BUY":
            valid_prices = (
                intent.stop_loss.price
                < intent.entry.price
                < intent.take_profit.price
            )
        else:
            valid_prices = (
                intent.take_profit.price
                < intent.entry.price
                < intent.stop_loss.price
            )
        if not valid_prices:
            raise PaperRuntimeError
        order_id = hashlib.sha256(
            canonical_json(
                {
                    "intent": json.loads(intent.to_json()),
                    "policy": self._policy_mapping(),
                    "source_sequence": source_sequence,
                }
            ).encode()
        ).hexdigest()
        baseline_sequence = source_sequence
        baseline_timestamp = intent.source_timestamp
        if self._latest_market is not None:
            baseline_sequence = max(
                baseline_sequence, self._latest_market.sequence
            )
            baseline_timestamp = max(
                baseline_timestamp, self._latest_market.timestamp
            )
        return _OrderRecord(
            order_id,
            intent.intent_id,
            intent.symbol,
            intent.exchange,
            intent.timeframe,
            intent.constraints_id,
            side,
            intent.entry.quantity,
            intent.entry.price,
            intent.stop_loss.price,
            intent.take_profit.price,
            Decimal(0),
            Decimal(0),
            Decimal(0),
            OrderStatus.SENT,
            intent.source_timestamp,
            source_sequence,
            baseline_sequence,
            baseline_timestamp,
        )

    @staticmethod
    def _prepare_protections(
        order: _OrderRecord,
    ) -> tuple[_ProtectionRecord, _ProtectionRecord]:
        stop_id = hashlib.sha256(
            f"{order.order_id}:stop_loss".encode()
        ).hexdigest()
        target_id = hashlib.sha256(
            f"{order.order_id}:take_profit".encode()
        ).hexdigest()
        side = "SELL" if order.side == "BUY" else "BUY"
        return (
            _ProtectionRecord(
                stop_id,
                order.order_id,
                target_id,
                order.intent_id,
                order.symbol,
                side,
                PaperProtectionKind.STOP_LOSS,
                order.stop_price,
                Decimal(0),
                Decimal(0),
                Decimal(0),
                OrderStatus.CREATED,
            ),
            _ProtectionRecord(
                target_id,
                order.order_id,
                stop_id,
                order.intent_id,
                order.symbol,
                side,
                PaperProtectionKind.TAKE_PROFIT,
                order.target_price,
                Decimal(0),
                Decimal(0),
                Decimal(0),
                OrderStatus.CREATED,
            ),
        )

    def _maybe_fill_entry(
        self,
        order: _OrderRecord,
        event: PaperMarketEvent,
        liquidity: Decimal,
    ) -> Decimal:
        if (
            event.sequence <= order.eligible_after_sequence
            or event.timestamp <= order.eligible_after_timestamp
        ):
            return liquidity
        eligible = (
            event.low <= order.limit_price
            if order.side == "BUY"
            else event.high >= order.limit_price
        )
        if not eligible:
            return liquidity
        quantity = min(
            order.quantity - order.filled_quantity,
            liquidity,
            self.policy.maximum_fill_quantity,
        )
        quantity = quantity.quantize(
            self.policy.quantity_quantum, rounding=ROUND_DOWN
        )
        if quantity < self.policy.minimum_executable_quantity:
            return liquidity
        self._apply_entry_fill(order, event, quantity, order.limit_price)
        return liquidity - quantity

    def _apply_entry_fill(
        self,
        order: _OrderRecord,
        event: PaperMarketEvent,
        quantity: Decimal,
        price: Decimal,
    ) -> None:
        fill = self._make_fill(
            order, event, quantity, price, False, "entry", order.side
        )
        previous_filled = order.filled_quantity
        order.filled_quantity += quantity
        order.fill_notional += quantity * price
        order.fees += fill.fee
        order.last_entry_sequence = event.sequence
        target_status = (
            OrderStatus.FILLED
            if order.filled_quantity == order.quantity
            else OrderStatus.PARTIALLY_FILLED
        )
        if not OrderTracker.can_transition(order.status, target_status):
            raise ValueError
        order.status = target_status
        margin = self._divide(
            quantity * order.limit_price, self.policy.leverage
        )
        self._account = self._account_after(
            reserved_delta=-margin,
            used_delta=margin,
            fee_delta=fill.fee,
            exposure_delta=quantity * price,
        )
        self._update_entry_position(order, quantity, price, event.price)
        self._fills.append(fill)
        self._publish(
            PaperEventType.ENTRY_FILL,
            order.order_id,
            fill.fill_id,
            event.sequence,
            {
                "fee": str(fill.fee),
                "price": str(fill.price),
                "quantity": str(fill.quantity),
                "status": order.status.value,
            },
        )
        self._activate_protections(order, quantity, event.sequence)
        self._hook("fill_recording")
        self._hook("position_update")
        self._hook("balance_update")
        self._hook("portfolio_update")
        self._hook("protective_activation")
        if order.filled_quantity < previous_filled:
            raise ValueError

    def _activate_protections(
        self,
        order: _OrderRecord,
        quantity: Decimal,
        market_sequence: int,
    ) -> None:
        for protection in self._protections.values():
            if protection.parent_order_id != order.order_id:
                continue
            if protection.status is OrderStatus.CREATED:
                if not OrderTracker.can_transition(
                    protection.status, OrderStatus.SENT
                ):
                    raise ValueError
                protection.status = OrderStatus.SENT
            if protection.status not in {
                OrderStatus.SENT,
                OrderStatus.PARTIALLY_FILLED,
            }:
                raise ValueError
            protection.active_quantity += quantity
            self._publish(
                PaperEventType.PROTECTION_ACTIVATED,
                protection.protection_id,
                None,
                market_sequence,
                {
                    "active_quantity": str(protection.active_quantity),
                    "kind": protection.kind.value,
                    "parent_order_id": order.order_id,
                    "quantity_delta": str(quantity),
                    "status": protection.status.value,
                },
            )

    def _maybe_fill_protection(
        self,
        order: _OrderRecord,
        position: _PositionRecord,
        event: PaperMarketEvent,
        liquidity: Decimal,
    ) -> Decimal:
        trigger_kind: PaperProtectionKind
        if position.side == "LONG":
            stop = event.low <= order.stop_price
            target = event.high >= order.target_price
            if stop:
                reference = min(order.stop_price, event.price)
                price = self._adverse(reference, "SELL")
                trigger = "stop_loss"
                trigger_kind = PaperProtectionKind.STOP_LOSS
            elif target:
                price = self._adverse(order.target_price, "SELL")
                trigger = "take_profit"
                trigger_kind = PaperProtectionKind.TAKE_PROFIT
            else:
                return liquidity
            side = "SELL"
        else:
            stop = event.high >= order.stop_price
            target = event.low <= order.target_price
            if stop:
                reference = max(order.stop_price, event.price)
                price = self._adverse(reference, "BUY")
                trigger = "stop_loss"
                trigger_kind = PaperProtectionKind.STOP_LOSS
            elif target:
                price = self._adverse(order.target_price, "BUY")
                trigger = "take_profit"
                trigger_kind = PaperProtectionKind.TAKE_PROFIT
            else:
                return liquidity
            side = "BUY"
        selected = next(
            item
            for item in self._protections.values()
            if item.parent_order_id == order.order_id
            and item.kind is trigger_kind
        )
        sibling = self._protections[selected.sibling_id]
        if selected.status not in {
            OrderStatus.SENT,
            OrderStatus.PARTIALLY_FILLED,
        }:
            return liquidity
        quantity = min(
            position.quantity,
            selected.active_quantity,
            liquidity,
            self.policy.maximum_fill_quantity,
        )
        quantity = quantity.quantize(
            self.policy.quantity_quantum, rounding=ROUND_DOWN
        )
        if quantity < self.policy.minimum_executable_quantity:
            return liquidity
        fill = self._make_fill(
            order,
            event,
            quantity,
            price,
            True,
            trigger,
            side,
            fill_order_id=selected.protection_id,
            parent_order_id=order.order_id,
        )
        self._apply_exit_fill(order, position, selected, sibling, fill)
        return liquidity - quantity

    def _apply_exit_fill(
        self,
        order: _OrderRecord,
        position: _PositionRecord,
        protection: _ProtectionRecord,
        sibling: _ProtectionRecord,
        fill: PaperFill,
    ) -> None:
        if (
            fill.quantity > position.quantity
            or fill.quantity > protection.active_quantity
            or fill.quantity > sibling.active_quantity
        ):
            raise ValueError
        if order.status in {
            OrderStatus.SENT,
            OrderStatus.PARTIALLY_FILLED,
        }:
            release = self._divide(
                order.remaining_quantity * order.limit_price,
                self.policy.leverage,
            )
            if not OrderTracker.can_transition(
                order.status, OrderStatus.CANCELLED
            ):
                raise ValueError
            order.status = OrderStatus.CANCELLED
            self._account = self._account_after(reserved_delta=-release)
            self._publish(
                PaperEventType.ORDER_CANCELED,
                order.order_id,
                None,
                fill.market_sequence,
                {
                    "reason": "protection_triggered",
                    "released_margin": str(release),
                    "remaining_quantity": str(order.remaining_quantity),
                },
            )
        direction = Decimal(1) if position.side == "LONG" else Decimal(-1)
        pnl = (
            (fill.price - position.average_entry_price)
            * fill.quantity
            * direction
        )
        released = self._divide(
            position.average_entry_price * fill.quantity,
            self.policy.leverage,
        )
        position.quantity -= fill.quantity
        position.realized_pnl += pnl
        position.mark_price = fill.price
        protection.active_quantity -= fill.quantity
        protection.filled_quantity += fill.quantity
        protection.fees += fill.fee
        sibling.active_quantity -= fill.quantity
        selected_status = (
            OrderStatus.FILLED
            if protection.active_quantity == 0
            else OrderStatus.PARTIALLY_FILLED
        )
        if not OrderTracker.can_transition(protection.status, selected_status):
            raise ValueError
        protection.status = selected_status
        if sibling.active_quantity == 0:
            if not OrderTracker.can_transition(
                sibling.status, OrderStatus.CANCELLED
            ):
                raise ValueError
            sibling.status = OrderStatus.CANCELLED
        self._account = self._account_after(
            used_delta=-released,
            fee_delta=fill.fee,
            realized_delta=pnl,
            exposure_delta=-(position.average_entry_price * fill.quantity),
        )
        self._fills.append(fill)
        self._publish(
            PaperEventType.PROTECTIVE_FILL,
            protection.protection_id,
            fill.fill_id,
            fill.market_sequence,
            {
                "fee": str(fill.fee),
                "parent_order_id": order.order_id,
                "price": str(fill.price),
                "quantity": str(fill.quantity),
                "status": protection.status.value,
                "trigger": protection.kind.value,
            },
        )
        sibling_event = (
            PaperEventType.PROTECTION_CANCELED
            if sibling.status is OrderStatus.CANCELLED
            else PaperEventType.PROTECTION_REDUCED
        )
        self._publish(
            sibling_event,
            sibling.protection_id,
            None,
            fill.market_sequence,
            {
                "active_quantity": str(sibling.active_quantity),
                "parent_order_id": order.order_id,
                "quantity_delta": str(-fill.quantity),
                "status": sibling.status.value,
            },
        )
        if position.quantity == 0:
            position.side = "FLAT"
        self._hook("fill_recording")
        self._hook("position_update")
        self._hook("balance_update")
        self._hook("portfolio_update")

    def _update_entry_position(
        self,
        order: _OrderRecord,
        quantity: Decimal,
        price: Decimal,
        mark: Decimal,
    ) -> None:
        side = "LONG" if order.side == "BUY" else "SHORT"
        position = self._positions.get(order.symbol)
        if position is None:
            self._positions[order.symbol] = _PositionRecord(
                order.symbol, side, quantity, price, Decimal(0), mark
            )
            return
        if position.side == "FLAT":
            position.side = side
            position.quantity = quantity
            position.average_entry_price = price
            position.mark_price = mark
            return
        if position.side != side:
            raise ValueError
        total = position.quantity + quantity
        position.average_entry_price = self._divide(
            position.average_entry_price * position.quantity
            + price * quantity,
            total,
        )
        position.quantity = total
        position.mark_price = mark

    def _mark_positions(self, event: PaperMarketEvent) -> None:
        position = self._positions.get(event.symbol)
        order = next(
            (
                item
                for item in self._orders.values()
                if item.symbol == event.symbol
            ),
            None,
        )
        if (
            position is not None
            and order is not None
            and order.exchange == event.exchange
            and order.timeframe == event.timeframe
        ):
            position.mark_price = event.price

    def _make_fill(
        self,
        order: _OrderRecord,
        event: PaperMarketEvent,
        quantity: Decimal,
        price: Decimal,
        protective: bool,
        trigger: str,
        side: str,
        *,
        fill_order_id: str | None = None,
        parent_order_id: str | None = None,
    ) -> PaperFill:
        normalized_price = price.quantize(
            self.policy.price_quantum, rounding=ROUND_HALF_EVEN
        )
        fee = (quantity * normalized_price * self.policy.fee_bps / 10000).quantize(
            self.policy.money_quantum, rounding=ROUND_HALF_EVEN
        )
        selected_order_id = fill_order_id or order.order_id
        fill_id = hashlib.sha256(
            (
                f"{selected_order_id}:{event.source_id}:{trigger}:"
                f"{len(self._fills)}:{quantity}:{normalized_price}"
            ).encode()
        ).hexdigest()
        if any(item.fill_id == fill_id for item in self._fills):
            raise ValueError
        SlippageCalculator.calculate(
            expected_price=float(price),
            executed_price=float(normalized_price),
            side=side,
        )
        return PaperFill(
            fill_id,
            selected_order_id,
            order.intent_id,
            order.symbol,
            IntentSide(side),
            quantity,
            normalized_price,
            fee,
            event.sequence,
            event.timestamp,
            protective,
            trigger,
            parent_order_id,
        )

    def _adverse(self, price: Decimal, side: str) -> Decimal:
        adjustment = self.policy.slippage_bps / Decimal(10000)
        factor = Decimal(1) + adjustment if side == "BUY" else Decimal(1) - adjustment
        return (price * factor).quantize(
            self.policy.price_quantum, rounding=ROUND_HALF_EVEN
        )

    @staticmethod
    def _divide(numerator: Decimal, denominator: Decimal) -> Decimal:
        with localcontext() as context:
            context.prec = 50
            context.rounding = ROUND_HALF_EVEN
            return numerator / denominator

    def _account_after(
        self,
        *,
        reserved_delta: Decimal = Decimal(0),
        used_delta: Decimal = Decimal(0),
        fee_delta: Decimal = Decimal(0),
        realized_delta: Decimal = Decimal(0),
        exposure_delta: Decimal = Decimal(0),
    ) -> PaperAccountSnapshot:
        reserved = self._account.reserved_margin + reserved_delta
        used = self._account.used_margin + used_delta
        fees = self._account.fees_paid + fee_delta
        realized = self._account.realized_pnl + realized_delta
        balance = self._account.starting_balance + realized - fees
        available = balance - reserved - used
        exposure = self._account.exposure + exposure_delta
        if min(reserved, used, fees, available, exposure) < 0:
            raise ValueError
        return PaperAccountSnapshot(
            self._account.starting_balance,
            balance,
            available,
            reserved,
            used,
            fees,
            realized,
            exposure,
            self._account.version + 1,
        )

    def _order_snapshot(self, order: _OrderRecord) -> PaperOrderSnapshot:
        average = (
            Decimal(0)
            if order.filled_quantity == 0
            else self._divide(order.fill_notional, order.filled_quantity)
        )
        return PaperOrderSnapshot(
            order.order_id,
            order.intent_id,
            order.symbol,
            IntentSide(order.side),
            order.quantity,
            order.limit_price,
            order.stop_price,
            order.target_price,
            order.filled_quantity,
            average,
            order.fees,
            order.status,
            order.source_timestamp,  # type: ignore[arg-type]
            order.source_sequence,
        )

    def _position_snapshot(
        self, position: _PositionRecord
    ) -> PaperPositionSnapshot:
        direction = (
            Decimal(1)
            if position.side == "LONG"
            else Decimal(-1) if position.side == "SHORT" else Decimal(0)
        )
        unrealized = (
            position.mark_price - position.average_entry_price
        ) * position.quantity * direction
        return PaperPositionSnapshot(
            position.symbol,
            position.side,
            position.quantity,
            position.average_entry_price,
            position.realized_pnl,
            unrealized,
            position.mark_price,
        )

    @staticmethod
    def _protection_snapshot(
        protection: _ProtectionRecord,
    ) -> PaperProtectionSnapshot:
        return PaperProtectionSnapshot(
            protection.protection_id,
            protection.parent_order_id,
            protection.sibling_id,
            protection.intent_id,
            protection.symbol,
            IntentSide(protection.side),
            protection.kind,
            protection.trigger_price,
            protection.active_quantity,
            protection.filled_quantity,
            protection.fees,
            protection.status,
        )

    @staticmethod
    def _flat_position(symbol: str) -> PaperPositionSnapshot:
        return PaperPositionSnapshot(
            symbol, "FLAT", Decimal(0), Decimal(0), Decimal(0), Decimal(0), Decimal(0)
        )

    def _publish(
        self,
        event_type: PaperEventType,
        order_id: str,
        fill_id: str | None,
        sequence: int | None,
        payload: dict[str, object] | None = None,
    ) -> None:
        selected_payload = {} if payload is None else payload
        payload_json = canonical_json(selected_payload)
        ledger_sequence = len(self._events) + 1
        previous_digest = self._events[-1].digest if self._events else ""
        event_id = hashlib.sha256(
            canonical_json(
                {
                    "event_type": event_type.value,
                    "fill_id": fill_id,
                    "ledger_sequence": ledger_sequence,
                    "market_sequence": sequence,
                    "order_id": order_id,
                    "payload": selected_payload,
                    "previous_digest": previous_digest,
                }
            ).encode()
        ).hexdigest()
        self._events.append(
            PaperLedgerEvent(
                event_id,
                event_type,
                order_id,
                fill_id,
                sequence,
                ledger_sequence,
                previous_digest,
                payload_json,
            )
        )

    def _hook(self, stage: str) -> None:
        if self._commit_hook is not None:
            self._commit_hook(stage)

    def _require_running(self) -> None:
        if not self._running:
            raise PaperRuntimeError

    def _private_state(self) -> _PrivateState:
        return deepcopy(
            (
                self._orders,
                self._intent_fingerprints,
                self._fills,
                self._events,
                self._positions,
                self._protections,
                self._account,
                self._latest_market,
            )
        )

    def _restore_private(self, state: _PrivateState) -> None:
        (
            self._orders,
            self._intent_fingerprints,
            self._fills,
            self._events,
            self._positions,
            self._protections,
            self._account,
            self._latest_market,
        ) = deepcopy(state)

    def _clear(self) -> None:
        self._orders.clear()
        self._intent_fingerprints.clear()
        self._fills.clear()
        self._events.clear()
        self._positions.clear()
        self._protections.clear()
        self._account = self._initial_account
        self._latest_market = None

    def _checkpoint_mapping(self) -> dict[str, object]:
        return {
            "account": account_mapping(self._account),
            "events": [
                {
                    "event_id": item.event_id,
                    "event_type": item.event_type.value,
                    "fill_id": item.fill_id,
                    "ledger_sequence": item.ledger_sequence,
                    "market_sequence": item.market_sequence,
                    "order_id": item.order_id,
                    "payload_json": item.payload_json,
                    "previous_digest": item.previous_digest,
                    "digest": item.digest,
                }
                for item in self._events
            ],
            "fills": [fill_mapping(item) for item in self._fills],
            "fingerprints": dict(sorted(self._intent_fingerprints.items())),
            "latest_market": (
                None
                if self._latest_market is None
                else market_mapping(self._latest_market)
            ),
            "orders": [
                {
                    **order_mapping(self._order_snapshot(item)),
                    "constraints_id": item.constraints_id,
                    "eligible_after_sequence": item.eligible_after_sequence,
                    "eligible_after_timestamp": (
                        item.eligible_after_timestamp.isoformat().replace(
                            "+00:00", "Z"
                        )
                    ),
                    "exchange": item.exchange,
                    "last_entry_sequence": item.last_entry_sequence,
                    "timeframe": item.timeframe,
                }
                for item in self._orders.values()
            ],
            "policy_id": self.policy.policy_id,
            "policy": self._policy_mapping(),
            "positions": [
                position_mapping(self._position_snapshot(item))
                for item in self._positions.values()
            ],
            "protections": [
                protection_mapping(self._protection_snapshot(item))
                for item in self._protections.values()
            ],
        }

    def _state_from_mapping(self, value: object) -> _PrivateState:
        try:
            if (
                not isinstance(value, dict)
                or value["policy_id"] != self.policy.policy_id
                or value["policy"] != self._policy_mapping()
            ):
                raise ValueError
            orders: dict[str, _OrderRecord] = {}
            for item in value["orders"]:
                order = _OrderRecord(
                    item["order_id"],
                    item["intent_id"],
                    item["symbol"],
                    item["exchange"],
                    item["timeframe"],
                    item["constraints_id"],
                    item["side"],
                    Decimal(item["quantity"]),
                    Decimal(item["limit_price"]),
                    Decimal(item["stop_price"]),
                    Decimal(item["target_price"]),
                    Decimal(item["filled_quantity"]),
                    Decimal(item["average_fill_price"])
                    * Decimal(item["filled_quantity"]),
                    Decimal(item["fees"]),
                    OrderStatus(item["status"]),
                    datetime_from_text(item["source_timestamp"]),
                    item["source_sequence"],
                    item["eligible_after_sequence"],
                    datetime_from_text(item["eligible_after_timestamp"]),
                    item["last_entry_sequence"],
                )
                self._order_snapshot(order)
                if order.order_id in orders:
                    raise ValueError
                orders[order.order_id] = order
            fills = [fill_from_mapping(item) for item in value["fills"]]
            events = [
                PaperLedgerEvent(
                    item["event_id"],
                    PaperEventType(item["event_type"]),
                    item["order_id"],
                    item["fill_id"],
                    item["market_sequence"],
                    item["ledger_sequence"],
                    item["previous_digest"],
                    item["payload_json"],
                    item["digest"],
                )
                for item in value["events"]
            ]
            positions: dict[str, _PositionRecord] = {}
            for item in value["positions"]:
                position = _PositionRecord(
                    item["symbol"],
                    item["side"],
                    Decimal(item["quantity"]),
                    Decimal(item["average_entry_price"]),
                    Decimal(item["realized_pnl"]),
                    Decimal(item["mark_price"]),
                )
                self._position_snapshot(position)
                if position.symbol in positions:
                    raise ValueError
                positions[position.symbol] = position
            protections: dict[str, _ProtectionRecord] = {}
            for item in value["protections"]:
                protection = protection_from_mapping(item)
                if protection.protection_id in protections:
                    raise ValueError
                self._protection_snapshot(protection)
                protections[protection.protection_id] = protection
            account = account_from_mapping(value["account"])
            fingerprints = dict(value["fingerprints"])
            latest_value = value["latest_market"]
            latest = (
                None
                if latest_value is None
                else market_from_mapping(latest_value)
            )
            state = (
                orders,
                fingerprints,
                fills,
                events,
                positions,
                protections,
                account,
                latest,
            )
            self._validate_prepared_state(state)
            probe = deepcopy(state)
        except Exception:
            raise PaperRuntimeError from None
        return probe

    def _policy_mapping(self) -> dict[str, object]:
        return {
            "constraints_id": self.policy.constraints_id,
            "fee_bps": str(self.policy.fee_bps),
            "leverage": str(self.policy.leverage),
            "maximum_fill_quantity": str(
                self.policy.maximum_fill_quantity
            ),
            "minimum_executable_quantity": str(
                self.policy.minimum_executable_quantity
            ),
            "money_quantum": str(self.policy.money_quantum),
            "policy_id": self.policy.policy_id,
            "price_quantum": str(self.policy.price_quantum),
            "quantity_quantum": str(self.policy.quantity_quantum),
            "slippage_bps": str(self.policy.slippage_bps),
        }

    def _validate_prepared_state(self, state: _PrivateState) -> None:
        (
            orders,
            fingerprints,
            fills,
            events,
            positions,
            protections,
            account,
            latest,
        ) = state
        intent_ids = {order.intent_id for order in orders.values()}
        if set(fingerprints) != intent_ids or any(
            not isinstance(value, str) or len(value) != 64
            for value in fingerprints.values()
        ):
            raise ValueError
        fill_ids = [fill.fill_id for fill in fills]
        if len(fill_ids) != len(set(fill_ids)):
            raise ValueError
        entry_fills: dict[str, list[PaperFill]] = {
            order_id: [] for order_id in orders
        }
        protection_fills: dict[str, list[PaperFill]] = {
            protection_id: [] for protection_id in protections
        }
        for fill in fills:
            if fill.protective:
                if (
                    fill.order_id not in protections
                    or fill.parent_order_id not in orders
                    or protections[fill.order_id].parent_order_id
                    != fill.parent_order_id
                ):
                    raise ValueError
                protection_fills[fill.order_id].append(fill)
            else:
                if fill.order_id not in orders:
                    raise ValueError
                entry_fills[fill.order_id].append(fill)
        for order_id, order in orders.items():
            selected = entry_fills[order_id]
            quantity = sum(
                (fill.quantity for fill in selected), Decimal(0)
            )
            notional = sum(
                (fill.quantity * fill.price for fill in selected), Decimal(0)
            )
            fees = sum((fill.fee for fill in selected), Decimal(0))
            if (
                quantity != order.filled_quantity
                or notional != order.fill_notional
                or fees != order.fees
                or order.remaining_quantity < 0
            ):
                raise ValueError
        for protection_id, protection in protections.items():
            selected = protection_fills[protection_id]
            if (
                protection.parent_order_id not in orders
                or protection.sibling_id not in protections
                or protections[protection.sibling_id].sibling_id
                != protection_id
                or protections[protection.sibling_id].parent_order_id
                != protection.parent_order_id
                or sum((fill.quantity for fill in selected), Decimal(0))
                != protection.filled_quantity
                or sum((fill.fee for fill in selected), Decimal(0))
                != protection.fees
            ):
                raise ValueError
        for order_id, order in orders.items():
            selected_protections = tuple(
                item
                for item in protections.values()
                if item.parent_order_id == order_id
            )
            position_quantity = (
                positions[order.symbol].quantity
                if order.symbol in positions
                else Decimal(0)
            )
            if (
                len(selected_protections) != 2
                or {item.kind for item in selected_protections}
                != {
                    PaperProtectionKind.STOP_LOSS,
                    PaperProtectionKind.TAKE_PROFIT,
                }
                or any(
                    item.active_quantity != position_quantity
                    for item in selected_protections
                )
            ):
                raise ValueError
        event_ids = [event.event_id for event in events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError
        previous_digest = ""
        fill_events: dict[str, int] = {}
        for index, event in enumerate(events, start=1):
            if (
                event.ledger_sequence != index
                or event.previous_digest != previous_digest
            ):
                raise ValueError
            previous_digest = event.digest
            if event.fill_id is not None:
                fill_events[event.fill_id] = (
                    fill_events.get(event.fill_id, 0) + 1
                )
        if any(fill_events.get(fill.fill_id) != 1 for fill in fills):
            raise ValueError
        accepted_orders = {
            event.order_id
            for event in events
            if event.event_type is PaperEventType.ORDER_ACCEPTED
        }
        if accepted_orders != set(orders):
            raise ValueError
        market_events = [
            event
            for event in events
            if event.event_type is PaperEventType.MARKET_ACCEPTED
        ]
        if latest is None:
            if market_events:
                raise ValueError
        elif (
            not market_events
            or market_events[-1].market_sequence != latest.sequence
            or json.loads(market_events[-1].payload_json)
            != market_mapping(latest)
        ):
            raise ValueError
        fees = sum((fill.fee for fill in fills), Decimal(0))
        realized = sum(
            (position.realized_pnl for position in positions.values()),
            Decimal(0),
        )
        reserved = sum(
            (
                self._divide(
                    order.remaining_quantity * order.limit_price,
                    self.policy.leverage,
                )
                for order in orders.values()
                if order.status
                in {OrderStatus.SENT, OrderStatus.PARTIALLY_FILLED}
            ),
            Decimal(0),
        )
        used = sum(
            (
                self._divide(
                    position.average_entry_price * position.quantity,
                    self.policy.leverage,
                )
                for position in positions.values()
            ),
            Decimal(0),
        )
        exposure = sum(
            (
                position.average_entry_price * position.quantity
                for position in positions.values()
            ),
            Decimal(0),
        )
        balance = account.starting_balance + realized - fees
        if (
            account.fees_paid != fees
            or account.realized_pnl != realized
            or account.reserved_margin != reserved
            or account.used_margin != used
            or account.exposure != exposure
            or account.balance != balance
            or account.available_balance != balance - reserved - used
        ):
            raise ValueError


def datetime_from_text(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fill_from_mapping(item: dict[str, object]) -> PaperFill:
    return PaperFill(
        str(item["fill_id"]),
        str(item["order_id"]),
        str(item["intent_id"]),
        str(item["symbol"]),
        IntentSide(str(item["side"])),
        Decimal(str(item["quantity"])),
        Decimal(str(item["price"])),
        Decimal(str(item["fee"])),
        int(str(item["market_sequence"])),
        datetime_from_text(str(item["market_timestamp"])),
        bool(item["protective"]),
        str(item["trigger"]),
        (
            None
            if item.get("parent_order_id") is None
            else str(item["parent_order_id"])
        ),
    )


def market_from_mapping(item: dict[str, object]) -> PaperMarketEvent:
    return PaperMarketEvent(
        int(str(item["sequence"])),
        str(item["symbol"]),
        datetime_from_text(str(item["timestamp"])),
        Decimal(str(item["price"])),
        Decimal(str(item["low"])),
        Decimal(str(item["high"])),
        Decimal(str(item["available_quantity"])),
        str(item["exchange"]),
        str(item["timeframe"]),
        str(item["source_id"]),
    )


def protection_from_mapping(item: dict[str, object]) -> _ProtectionRecord:
    return _ProtectionRecord(
        str(item["protection_id"]),
        str(item["parent_order_id"]),
        str(item["sibling_id"]),
        str(item["intent_id"]),
        str(item["symbol"]),
        str(item["side"]),
        PaperProtectionKind(str(item["kind"])),
        Decimal(str(item["trigger_price"])),
        Decimal(str(item["active_quantity"])),
        Decimal(str(item["filled_quantity"])),
        Decimal(str(item["fees"])),
        OrderStatus(str(item["status"])),
    )


def account_from_mapping(item: dict[str, object]) -> PaperAccountSnapshot:
    return PaperAccountSnapshot(
        Decimal(str(item["starting_balance"])),
        Decimal(str(item["balance"])),
        Decimal(str(item["available_balance"])),
        Decimal(str(item["reserved_margin"])),
        Decimal(str(item["used_margin"])),
        Decimal(str(item["fees_paid"])),
        Decimal(str(item["realized_pnl"])),
        Decimal(str(item["exposure"])),
        int(str(item["version"])),
    )


__all__ = (
    "PAPER_EXECUTION_SERVICE_ID",
    "PaperExecutionCoordinator",
    "PaperRuntimeError",
)
