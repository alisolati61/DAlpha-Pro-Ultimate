"""Immutable deterministic paper-runtime contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum

from src.execution.order_tracker import OrderStatus
from src.execution_intent.models import IntentSide, decimal_text, decimal_value


class PaperReason(str, Enum):
    ACCEPTED = "accepted"
    EXISTING_SUBMISSION = "existing_submission"
    INTENT_NOT_READY = "intent_not_ready"
    INVALID_INTENT = "invalid_intent"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    DUPLICATE_CONFLICT = "duplicate_conflict"
    UNSUPPORTED_ORDER_TYPE = "unsupported_order_type"
    CANCELED = "canceled"
    TERMINAL_ORDER = "terminal_order"


class PaperEventType(str, Enum):
    ORDER_CREATED = "order_created"
    ORDER_ACCEPTED = "order_accepted"
    MARKET_ACCEPTED = "market_accepted"
    ENTRY_FILL = "entry_fill"
    PROTECTION_ACTIVATED = "protection_activated"
    PROTECTIVE_FILL = "protective_fill"
    PROTECTION_REDUCED = "protection_reduced"
    PROTECTION_CANCELED = "protection_canceled"
    ORDER_CANCELED = "order_canceled"


class PaperProtectionKind(str, Enum):
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class ReconciliationStatus(str, Enum):
    MATCHED = "MATCHED"
    MISMATCH = "MISMATCH"


class ReconciliationReason(str, Enum):
    MATCHED = "matched"
    FILLED_QUANTITY_MISMATCH = "filled_quantity_mismatch"
    REMAINING_QUANTITY_MISMATCH = "remaining_quantity_mismatch"
    AVERAGE_PRICE_MISMATCH = "average_price_mismatch"
    FEE_MISMATCH = "fee_mismatch"
    POSITION_QUANTITY_MISMATCH = "position_quantity_mismatch"
    REALIZED_PNL_MISMATCH = "realized_pnl_mismatch"
    BALANCE_MISMATCH = "balance_mismatch"
    EXPOSURE_MISMATCH = "exposure_mismatch"
    DUPLICATE_FILL_ID = "duplicate_fill_id"
    DUPLICATE_LEDGER_EVENT = "duplicate_ledger_event"
    ORPHAN_PROTECTIVE_ORDER = "orphan_protective_order"
    OVER_CLOSE = "over_close"
    MISSING_LEDGER_EVENT = "missing_ledger_event"


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("timestamp must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is invalid")
    return value.strip()


def _non_negative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} is invalid")
    return value


def _signed_decimal(value: object, name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} is invalid")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{name} is invalid") from error
    if not number.is_finite():
        raise ValueError(f"{name} is invalid")
    return number.normalize()


@dataclass(frozen=True, slots=True)
class PaperExecutionPolicy:
    policy_id: str
    slippage_bps: Decimal
    fee_bps: Decimal
    maximum_fill_quantity: Decimal
    minimum_executable_quantity: Decimal
    leverage: Decimal
    constraints_id: str | None = None
    price_quantum: Decimal = Decimal("0.00000001")
    quantity_quantum: Decimal = Decimal("0.00000001")
    money_quantum: Decimal = Decimal("0.00000001")

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _text(self.policy_id, "policy_id"))
        for name in ("slippage_bps", "fee_bps"):
            object.__setattr__(
                self, name, decimal_value(getattr(self, name), name, zero=True)
            )
        for name in (
            "maximum_fill_quantity",
            "minimum_executable_quantity",
            "leverage",
            "price_quantum",
            "quantity_quantum",
            "money_quantum",
        ):
            object.__setattr__(
                self, name, decimal_value(getattr(self, name), name)
            )
        if self.constraints_id is not None:
            object.__setattr__(
                self,
                "constraints_id",
                _text(self.constraints_id, "constraints_id"),
            )
        if self.minimum_executable_quantity > self.maximum_fill_quantity:
            raise ValueError("fill quantity policy is invalid")


@dataclass(frozen=True, slots=True)
class PaperMarketEvent:
    sequence: int
    symbol: str
    timestamp: datetime
    price: Decimal
    low: Decimal
    high: Decimal
    available_quantity: Decimal
    exchange: str = "recorded"
    timeframe: str = "1m"
    source_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "sequence", _non_negative_int(self.sequence, "sequence")
        )
        object.__setattr__(self, "symbol", _text(self.symbol, "symbol"))
        object.__setattr__(self, "timestamp", _utc(self.timestamp))
        for name in ("price", "low", "high"):
            object.__setattr__(
                self, name, decimal_value(getattr(self, name), name)
            )
        object.__setattr__(
            self,
            "available_quantity",
            decimal_value(
                self.available_quantity, "available_quantity", zero=True
            ),
        )
        if not self.low <= self.price <= self.high:
            raise ValueError("market range is inconsistent")
        object.__setattr__(self, "exchange", _text(self.exchange, "exchange"))
        object.__setattr__(self, "timeframe", _text(self.timeframe, "timeframe"))
        if self.source_id is None:
            source = canonical_json(
                {
                    "available_quantity": decimal_text(
                        self.available_quantity
                    ),
                    "exchange": self.exchange,
                    "high": decimal_text(self.high),
                    "low": decimal_text(self.low),
                    "price": decimal_text(self.price),
                    "sequence": self.sequence,
                    "symbol": self.symbol,
                    "timeframe": self.timeframe,
                    "timestamp": self.timestamp.isoformat().replace(
                        "+00:00", "Z"
                    ),
                }
            )
            object.__setattr__(
                self, "source_id", hashlib.sha256(source.encode()).hexdigest()
            )
        else:
            object.__setattr__(
                self, "source_id", _text(self.source_id, "source_id")
            )


@dataclass(frozen=True, slots=True)
class PaperOrderSnapshot:
    order_id: str
    intent_id: str
    symbol: str
    side: IntentSide
    quantity: Decimal
    limit_price: Decimal
    stop_price: Decimal
    target_price: Decimal
    filled_quantity: Decimal
    average_fill_price: Decimal
    fees: Decimal
    status: OrderStatus
    source_timestamp: datetime
    source_sequence: int

    @property
    def remaining_quantity(self) -> Decimal:
        return self.quantity - self.filled_quantity

    def __post_init__(self) -> None:
        for name in ("order_id", "intent_id", "symbol"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        try:
            object.__setattr__(self, "side", IntentSide(self.side))
        except (TypeError, ValueError) as error:
            raise ValueError("side is invalid") from error
        for name in ("quantity", "limit_price", "stop_price", "target_price"):
            object.__setattr__(
                self, name, decimal_value(getattr(self, name), name)
            )
        for name in ("filled_quantity", "average_fill_price", "fees"):
            object.__setattr__(
                self,
                name,
                decimal_value(getattr(self, name), name, zero=True),
            )
        if self.filled_quantity > self.quantity:
            raise ValueError("filled quantity exceeds order quantity")
        if self.filled_quantity == 0 and self.average_fill_price != 0:
            raise ValueError("average price is inconsistent")
        if not isinstance(self.status, OrderStatus):
            raise TypeError("status is invalid")
        if (
            self.status in {
                OrderStatus.CREATED,
                OrderStatus.SENT,
                OrderStatus.REJECTED,
            }
            and self.filled_quantity != 0
        ):
            raise ValueError("order lifecycle is inconsistent")
        if self.status is OrderStatus.PARTIALLY_FILLED and not (
            Decimal(0) < self.filled_quantity < self.quantity
        ):
            raise ValueError("order lifecycle is inconsistent")
        if (
            self.status is OrderStatus.FILLED
            and self.filled_quantity != self.quantity
        ):
            raise ValueError("order lifecycle is inconsistent")
        if (
            self.status is OrderStatus.CANCELLED
            and self.filled_quantity == self.quantity
        ):
            raise ValueError("order lifecycle is inconsistent")
        object.__setattr__(self, "source_timestamp", _utc(self.source_timestamp))
        object.__setattr__(
            self,
            "source_sequence",
            _non_negative_int(self.source_sequence, "source_sequence"),
        )


@dataclass(frozen=True, slots=True)
class PaperFill:
    fill_id: str
    order_id: str
    intent_id: str
    symbol: str
    side: IntentSide
    quantity: Decimal
    price: Decimal
    fee: Decimal
    market_sequence: int
    market_timestamp: datetime
    protective: bool
    trigger: str
    parent_order_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("fill_id", "order_id", "intent_id", "symbol", "trigger"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        try:
            object.__setattr__(self, "side", IntentSide(self.side))
        except (TypeError, ValueError) as error:
            raise ValueError("side is invalid") from error
        object.__setattr__(self, "quantity", decimal_value(self.quantity, "quantity"))
        object.__setattr__(self, "price", decimal_value(self.price, "price"))
        object.__setattr__(
            self, "fee", decimal_value(self.fee, "fee", zero=True)
        )
        object.__setattr__(
            self,
            "market_sequence",
            _non_negative_int(self.market_sequence, "market_sequence"),
        )
        object.__setattr__(
            self, "market_timestamp", _utc(self.market_timestamp)
        )
        if not isinstance(self.protective, bool):
            raise TypeError("protective is invalid")
        if self.parent_order_id is not None:
            object.__setattr__(
                self,
                "parent_order_id",
                _text(self.parent_order_id, "parent_order_id"),
            )
        if self.protective and self.parent_order_id is None:
            raise ValueError("protective fill requires parent_order_id")
        if not self.protective and self.parent_order_id is not None:
            raise ValueError("entry fill cannot have parent_order_id")
        if self.protective and self.trigger not in {
            PaperProtectionKind.STOP_LOSS.value,
            PaperProtectionKind.TAKE_PROFIT.value,
        }:
            raise ValueError("protective trigger is invalid")
        if not self.protective and self.trigger != "entry":
            raise ValueError("entry trigger is invalid")


@dataclass(frozen=True, slots=True)
class PaperPositionSnapshot:
    symbol: str
    side: str
    quantity: Decimal
    average_entry_price: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    mark_price: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", _text(self.symbol, "symbol"))
        if self.side not in {"LONG", "SHORT", "FLAT"}:
            raise ValueError("side is invalid")
        object.__setattr__(
            self, "quantity", decimal_value(self.quantity, "quantity", zero=True)
        )
        for name in ("realized_pnl", "unrealized_pnl"):
            object.__setattr__(
                self, name, _signed_decimal(getattr(self, name), name)
            )
        for name in ("average_entry_price", "mark_price"):
            object.__setattr__(
                self, name, decimal_value(getattr(self, name), name, zero=True)
            )
        if self.quantity == 0 and self.side != "FLAT":
            raise ValueError("flat quantity requires FLAT side")
        if self.quantity != 0 and self.side == "FLAT":
            raise ValueError("FLAT side requires zero quantity")


@dataclass(frozen=True, slots=True)
class PaperAccountSnapshot:
    starting_balance: Decimal
    balance: Decimal
    available_balance: Decimal
    reserved_margin: Decimal
    used_margin: Decimal
    fees_paid: Decimal
    realized_pnl: Decimal
    exposure: Decimal
    version: int

    def __post_init__(self) -> None:
        for name in (
            "starting_balance",
            "balance",
            "available_balance",
            "reserved_margin",
            "used_margin",
            "fees_paid",
            "exposure",
        ):
            object.__setattr__(
                self, name, decimal_value(getattr(self, name), name, zero=True)
            )
        object.__setattr__(
            self, "realized_pnl", _signed_decimal(self.realized_pnl, "realized_pnl")
        )
        object.__setattr__(
            self, "version", _non_negative_int(self.version, "version")
        )


@dataclass(frozen=True, slots=True)
class PaperLedgerEvent:
    event_id: str
    event_type: PaperEventType
    order_id: str
    fill_id: str | None
    market_sequence: int | None
    ledger_sequence: int = 0
    previous_digest: str = ""
    payload_json: str = "{}"
    digest: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", _text(self.event_id, "event_id"))
        if not isinstance(self.event_type, PaperEventType):
            raise TypeError("event_type is invalid")
        object.__setattr__(self, "order_id", _text(self.order_id, "order_id"))
        if self.fill_id is not None:
            object.__setattr__(self, "fill_id", _text(self.fill_id, "fill_id"))
        if self.market_sequence is not None:
            object.__setattr__(
                self,
                "market_sequence",
                _non_negative_int(self.market_sequence, "market_sequence"),
            )
        object.__setattr__(
            self,
            "ledger_sequence",
            _non_negative_int(self.ledger_sequence, "ledger_sequence"),
        )
        if not isinstance(self.previous_digest, str):
            raise TypeError("previous_digest is invalid")
        try:
            payload = json.loads(self.payload_json)
        except (TypeError, ValueError) as error:
            raise ValueError("ledger payload is invalid") from error
        if (
            not isinstance(payload, dict)
            or canonical_json(payload) != self.payload_json
        ):
            raise ValueError("ledger payload is invalid")
        unsigned = canonical_json(
            {
                "event_id": self.event_id,
                "event_type": self.event_type.value,
                "fill_id": self.fill_id,
                "ledger_sequence": self.ledger_sequence,
                "market_sequence": self.market_sequence,
                "order_id": self.order_id,
                "payload": payload,
                "previous_digest": self.previous_digest,
            }
        )
        expected = hashlib.sha256(unsigned.encode()).hexdigest()
        if self.digest:
            if self.digest != expected:
                raise ValueError("ledger digest is invalid")
        else:
            object.__setattr__(self, "digest", expected)


@dataclass(frozen=True, slots=True)
class PaperProtectionSnapshot:
    protection_id: str
    parent_order_id: str
    sibling_id: str
    intent_id: str
    symbol: str
    side: IntentSide
    kind: PaperProtectionKind
    trigger_price: Decimal
    active_quantity: Decimal
    filled_quantity: Decimal
    fees: Decimal
    status: OrderStatus
    reduce_only: bool = True

    def __post_init__(self) -> None:
        for name in (
            "protection_id",
            "parent_order_id",
            "sibling_id",
            "intent_id",
            "symbol",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        try:
            object.__setattr__(self, "side", IntentSide(self.side))
        except (TypeError, ValueError) as error:
            raise ValueError("side is invalid") from error
        if not isinstance(self.kind, PaperProtectionKind):
            raise TypeError("kind is invalid")
        for name in ("trigger_price",):
            object.__setattr__(
                self, name, decimal_value(getattr(self, name), name)
            )
        for name in ("active_quantity", "filled_quantity", "fees"):
            object.__setattr__(
                self,
                name,
                decimal_value(getattr(self, name), name, zero=True),
            )
        if not isinstance(self.status, OrderStatus):
            raise TypeError("status is invalid")
        if self.reduce_only is not True:
            raise ValueError("protection must be reduce-only")
        if self.status is OrderStatus.CREATED and any(
            value != 0
            for value in (
                self.active_quantity,
                self.filled_quantity,
                self.fees,
            )
        ):
            raise ValueError("protection lifecycle is inconsistent")
        if self.status is OrderStatus.SENT and self.active_quantity == 0:
            raise ValueError("protection lifecycle is inconsistent")
        if self.status is OrderStatus.PARTIALLY_FILLED and (
            self.active_quantity == 0 or self.filled_quantity == 0
        ):
            raise ValueError("protection lifecycle is inconsistent")
        if self.status is OrderStatus.FILLED and (
            self.active_quantity != 0 or self.filled_quantity == 0
        ):
            raise ValueError("protection lifecycle is inconsistent")
        if (
            self.status is OrderStatus.CANCELLED
            and self.active_quantity != 0
        ):
            raise ValueError("protection lifecycle is inconsistent")


@dataclass(frozen=True, slots=True)
class PaperSubmissionResult:
    accepted: bool
    reason: PaperReason
    order: PaperOrderSnapshot | None

    def __post_init__(self) -> None:
        if not isinstance(self.accepted, bool):
            raise TypeError("accepted is invalid")
        if not isinstance(self.reason, PaperReason):
            raise TypeError("reason is invalid")
        if self.order is not None and not isinstance(self.order, PaperOrderSnapshot):
            raise TypeError("order is invalid")


@dataclass(frozen=True, slots=True)
class PaperExecutionReport:
    order: PaperOrderSnapshot
    fills: tuple[PaperFill, ...]
    position: PaperPositionSnapshot
    account: PaperAccountSnapshot
    events: tuple[PaperLedgerEvent, ...]
    protections: tuple[PaperProtectionSnapshot, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.order, PaperOrderSnapshot):
            raise TypeError("order is invalid")
        if not isinstance(self.position, PaperPositionSnapshot):
            raise TypeError("position is invalid")
        if not isinstance(self.account, PaperAccountSnapshot):
            raise TypeError("account is invalid")
        fills = tuple(self.fills)
        events = tuple(self.events)
        protections = tuple(self.protections)
        if any(not isinstance(item, PaperFill) for item in fills):
            raise TypeError("fills are invalid")
        if any(not isinstance(item, PaperLedgerEvent) for item in events):
            raise TypeError("events are invalid")
        if any(
            not isinstance(item, PaperProtectionSnapshot)
            for item in protections
        ):
            raise TypeError("protections are invalid")
        object.__setattr__(self, "fills", fills)
        object.__setattr__(self, "events", events)
        object.__setattr__(self, "protections", protections)

    def to_json(self) -> str:
        return canonical_json(report_mapping(self))

    @property
    def report_id(self) -> str:
        return hashlib.sha256(self.to_json().encode()).hexdigest()

    @property
    def equity(self) -> Decimal:
        return self.account.balance + self.position.unrealized_pnl


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    status: ReconciliationStatus
    reasons: tuple[ReconciliationReason, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, ReconciliationStatus):
            raise TypeError("reconciliation status is invalid")
        if any(not isinstance(item, ReconciliationReason) for item in self.reasons):
            raise TypeError("reconciliation reasons are invalid")
        reasons = tuple(sorted(set(self.reasons), key=lambda item: item.value))
        if not reasons:
            raise ValueError("reconciliation reasons are required")
        if self.status is ReconciliationStatus.MATCHED and reasons != (
            ReconciliationReason.MATCHED,
        ):
            raise ValueError("matched reconciliation reasons are invalid")
        if self.status is ReconciliationStatus.MISMATCH and (
            ReconciliationReason.MATCHED in reasons
        ):
            raise ValueError("mismatch reconciliation reasons are invalid")
        object.__setattr__(self, "reasons", reasons)


@dataclass(frozen=True, slots=True)
class PaperCheckpoint:
    policy_id: str
    version: int
    payload_json: str
    digest: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "policy_id", _text(self.policy_id, "checkpoint policy_id")
        )
        object.__setattr__(
            self, "version", _non_negative_int(self.version, "checkpoint version")
        )
        try:
            parsed = json.loads(self.payload_json)
        except (TypeError, ValueError) as error:
            raise ValueError("checkpoint payload is invalid") from error
        if not isinstance(parsed, dict):
            raise ValueError("checkpoint payload is invalid")
        canonical = canonical_json(parsed)
        if canonical != self.payload_json:
            raise ValueError("checkpoint payload is not canonical")
        expected = hashlib.sha256(
            f"{self.policy_id}:{self.version}:{canonical}".encode()
        ).hexdigest()
        if self.digest != expected:
            raise ValueError("checkpoint digest is invalid")


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def report_mapping(report: PaperExecutionReport) -> dict[str, object]:
    return {
        "account": account_mapping(report.account),
        "equity": decimal_text(report.equity),
        "events": [
            {
                "event_id": item.event_id,
                "event_type": item.event_type.value,
                "fill_id": item.fill_id,
                "ledger_sequence": item.ledger_sequence,
                "market_sequence": item.market_sequence,
                "order_id": item.order_id,
                "payload": json.loads(item.payload_json),
                "previous_digest": item.previous_digest,
                "digest": item.digest,
            }
            for item in report.events
        ],
        "fills": [fill_mapping(item) for item in report.fills],
        "order": order_mapping(report.order),
        "position": position_mapping(report.position),
        "protections": [
            protection_mapping(item) for item in report.protections
        ],
    }


def market_mapping(event: PaperMarketEvent) -> dict[str, object]:
    return {
        "available_quantity": decimal_text(event.available_quantity),
        "exchange": event.exchange,
        "high": decimal_text(event.high),
        "low": decimal_text(event.low),
        "price": decimal_text(event.price),
        "sequence": event.sequence,
        "source_id": event.source_id,
        "symbol": event.symbol,
        "timeframe": event.timeframe,
        "timestamp": event.timestamp.isoformat().replace("+00:00", "Z"),
    }


def order_mapping(order: PaperOrderSnapshot) -> dict[str, object]:
    return {
        "average_fill_price": decimal_text(order.average_fill_price),
        "fees": decimal_text(order.fees),
        "filled_quantity": decimal_text(order.filled_quantity),
        "intent_id": order.intent_id,
        "limit_price": decimal_text(order.limit_price),
        "order_id": order.order_id,
        "quantity": decimal_text(order.quantity),
        "side": order.side.value,
        "source_sequence": order.source_sequence,
        "source_timestamp": order.source_timestamp.isoformat().replace("+00:00", "Z"),
        "status": order.status.value,
        "stop_price": decimal_text(order.stop_price),
        "symbol": order.symbol,
        "target_price": decimal_text(order.target_price),
    }


def fill_mapping(fill: PaperFill) -> dict[str, object]:
    return {
        "fee": decimal_text(fill.fee),
        "fill_id": fill.fill_id,
        "intent_id": fill.intent_id,
        "market_sequence": fill.market_sequence,
        "market_timestamp": fill.market_timestamp.isoformat().replace(
            "+00:00", "Z"
        ),
        "order_id": fill.order_id,
        "price": decimal_text(fill.price),
        "protective": fill.protective,
        "quantity": decimal_text(fill.quantity),
        "side": fill.side.value,
        "symbol": fill.symbol,
        "trigger": fill.trigger,
        "parent_order_id": fill.parent_order_id,
    }


def position_mapping(position: PaperPositionSnapshot) -> dict[str, object]:
    return {
        "average_entry_price": decimal_text(position.average_entry_price),
        "mark_price": decimal_text(position.mark_price),
        "quantity": decimal_text(position.quantity),
        "realized_pnl": decimal_text(position.realized_pnl),
        "side": position.side,
        "symbol": position.symbol,
        "unrealized_pnl": decimal_text(position.unrealized_pnl),
    }


def account_mapping(account: PaperAccountSnapshot) -> dict[str, object]:
    return {
        "available_balance": decimal_text(account.available_balance),
        "balance": decimal_text(account.balance),
        "exposure": decimal_text(account.exposure),
        "fees_paid": decimal_text(account.fees_paid),
        "realized_pnl": decimal_text(account.realized_pnl),
        "reserved_margin": decimal_text(account.reserved_margin),
        "starting_balance": decimal_text(account.starting_balance),
        "used_margin": decimal_text(account.used_margin),
        "version": account.version,
    }


def protection_mapping(
    protection: PaperProtectionSnapshot,
) -> dict[str, object]:
    return {
        "active_quantity": decimal_text(protection.active_quantity),
        "fees": decimal_text(protection.fees),
        "filled_quantity": decimal_text(protection.filled_quantity),
        "intent_id": protection.intent_id,
        "kind": protection.kind.value,
        "parent_order_id": protection.parent_order_id,
        "protection_id": protection.protection_id,
        "reduce_only": protection.reduce_only,
        "side": protection.side.value,
        "sibling_id": protection.sibling_id,
        "status": protection.status.value,
        "symbol": protection.symbol,
        "trigger_price": decimal_text(protection.trigger_price),
    }


__all__ = (
    "PaperAccountSnapshot",
    "PaperCheckpoint",
    "PaperEventType",
    "PaperExecutionPolicy",
    "PaperExecutionReport",
    "PaperFill",
    "PaperLedgerEvent",
    "PaperMarketEvent",
    "PaperOrderSnapshot",
    "PaperPositionSnapshot",
    "PaperProtectionKind",
    "PaperProtectionSnapshot",
    "PaperReason",
    "PaperSubmissionResult",
    "ReconciliationReason",
    "ReconciliationResult",
    "ReconciliationStatus",
    "account_mapping",
    "canonical_json",
    "fill_mapping",
    "market_mapping",
    "order_mapping",
    "position_mapping",
    "protection_mapping",
)
