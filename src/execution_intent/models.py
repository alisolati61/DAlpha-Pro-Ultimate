"""Immutable local contracts for deterministic execution intent planning."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum


class IntentStatus(str, Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    NO_ACTION = "NO_ACTION"


class IntentReason(str, Enum):
    DECISION_HOLD = "decision_hold"
    DECISION_REJECTED = "decision_rejected"
    INVALID_DECISION = "invalid_decision"
    INVALID_PRICE_RELATIONSHIP = "invalid_price_relationship"
    INVALID_RISK_DISTANCE = "invalid_risk_distance"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    EXPOSURE_LIMIT = "exposure_limit"
    QUANTITY_BELOW_MINIMUM = "quantity_below_minimum"
    QUANTITY_ABOVE_MAXIMUM = "quantity_above_maximum"
    NOTIONAL_BELOW_MINIMUM = "notional_below_minimum"
    NORMALIZATION_INVALIDATED_PROTECTION = (
        "normalization_invalidated_protection"
    )
    EXECUTION_CONTRACT_INCOMPATIBLE = "execution_contract_incompatible"
    DUPLICATE_CONFLICT = "duplicate_conflict"
    INTENT_READY = "intent_ready"


class IntentSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class IntentOrderType(str, Enum):
    LIMIT = "LIMIT"
    STOP = "STOP"
    TAKE_PROFIT = "TAKE_PROFIT"


class IntentTimeInForce(str, Enum):
    GTC = "GTC"


def decimal_value(value: object, name: str, *, zero: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} is invalid")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{name} is invalid") from error
    if not number.is_finite() or number < 0 or (not zero and number == 0):
        raise ValueError(f"{name} is invalid")
    return number.normalize()


def decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


@dataclass(frozen=True, slots=True)
class AccountExecutionSnapshot:
    equity: Decimal
    available_balance: Decimal
    current_exposure: Decimal
    open_position_quantity: Decimal
    version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "equity", decimal_value(self.equity, "equity"))
        object.__setattr__(
            self,
            "available_balance",
            decimal_value(self.available_balance, "available_balance", zero=True),
        )
        object.__setattr__(
            self,
            "current_exposure",
            decimal_value(self.current_exposure, "current_exposure", zero=True),
        )
        object.__setattr__(
            self,
            "open_position_quantity",
            decimal_value(
                self.open_position_quantity, "open_position_quantity", zero=True
            ),
        )
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("version is invalid")
        object.__setattr__(self, "version", self.version.strip())


@dataclass(frozen=True, slots=True)
class ApprovedRiskSnapshot:
    decision_id: str
    maximum_quantity: Decimal
    risk_percent: Decimal
    leverage: Decimal
    risk_reference: str

    def __post_init__(self) -> None:
        for name in ("decision_id", "risk_reference"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is invalid")
            object.__setattr__(self, name, value.strip())
        maximum = decimal_value(self.maximum_quantity, "maximum_quantity")
        risk = decimal_value(self.risk_percent, "risk_percent")
        leverage = decimal_value(self.leverage, "leverage")
        if risk > 100:
            raise ValueError("risk_percent is invalid")
        object.__setattr__(self, "maximum_quantity", maximum)
        object.__setattr__(self, "risk_percent", risk)
        object.__setattr__(self, "leverage", leverage)


@dataclass(frozen=True, slots=True)
class InstrumentConstraints:
    symbol: str
    exchange: str
    price_tick: Decimal
    quantity_step: Decimal
    minimum_quantity: Decimal
    minimum_notional: Decimal
    maximum_quantity: Decimal | None
    constraints_id: str

    def __post_init__(self) -> None:
        for name in ("symbol", "exchange", "constraints_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is invalid")
            object.__setattr__(self, name, value.strip())
        for name in (
            "price_tick",
            "quantity_step",
            "minimum_quantity",
            "minimum_notional",
        ):
            object.__setattr__(
                self, name, decimal_value(getattr(self, name), name)
            )
        if self.maximum_quantity is not None:
            maximum = decimal_value(self.maximum_quantity, "maximum_quantity")
            if maximum < self.minimum_quantity:
                raise ValueError("maximum_quantity is invalid")
            object.__setattr__(self, "maximum_quantity", maximum)


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    risk_percent: Decimal
    leverage: Decimal
    maximum_exposure_ratio: Decimal

    def __post_init__(self) -> None:
        risk = decimal_value(self.risk_percent, "risk_percent")
        leverage = decimal_value(self.leverage, "leverage")
        exposure = decimal_value(
            self.maximum_exposure_ratio, "maximum_exposure_ratio"
        )
        if risk > 100 or exposure > 1:
            raise ValueError("execution policy is invalid")
        object.__setattr__(self, "risk_percent", risk)
        object.__setattr__(self, "leverage", leverage)
        object.__setattr__(self, "maximum_exposure_ratio", exposure)


@dataclass(frozen=True, slots=True)
class OrderSpecification:
    side: IntentSide
    order_type: IntentOrderType
    price: Decimal
    quantity: Decimal
    time_in_force: IntentTimeInForce
    reduce_only: bool

    def __post_init__(self) -> None:
        if not isinstance(self.side, IntentSide):
            raise TypeError("side is invalid")
        if not isinstance(self.order_type, IntentOrderType):
            raise TypeError("order_type is invalid")
        if not isinstance(self.time_in_force, IntentTimeInForce):
            raise TypeError("time_in_force is invalid")
        if not isinstance(self.reduce_only, bool):
            raise TypeError("reduce_only is invalid")
        object.__setattr__(self, "price", decimal_value(self.price, "price"))
        object.__setattr__(
            self, "quantity", decimal_value(self.quantity, "quantity")
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "order_type": self.order_type.value,
            "price": decimal_text(self.price),
            "quantity": decimal_text(self.quantity),
            "reduce_only": self.reduce_only,
            "side": self.side.value,
            "time_in_force": self.time_in_force.value,
        }


@dataclass(frozen=True, slots=True)
class ExecutionIntent:
    intent_id: str
    decision_id: str
    status: IntentStatus
    symbol: str | None
    exchange: str | None
    timeframe: str | None
    entry: OrderSpecification | None
    stop_loss: OrderSpecification | None
    take_profit: OrderSpecification | None
    strategy_id: str | None
    strategy_version: str | None
    risk_amount: Decimal | None
    constraints_id: str | None
    source_timestamp: datetime | None
    reason_codes: tuple[IntentReason, ...]

    def __post_init__(self) -> None:
        if not self.intent_id or not self.decision_id:
            raise ValueError("intent identifiers are invalid")
        reasons = tuple(sorted(set(self.reason_codes), key=lambda item: item.value))
        if not reasons:
            raise ValueError("reason_codes are required")
        if self.status is IntentStatus.READY:
            required = (
                self.symbol,
                self.exchange,
                self.timeframe,
                self.entry,
                self.stop_loss,
                self.take_profit,
                self.strategy_id,
                self.strategy_version,
                self.risk_amount,
                self.constraints_id,
                self.source_timestamp,
            )
            if any(value is None for value in required):
                raise ValueError("READY intent is incomplete")
        if self.risk_amount is not None:
            object.__setattr__(
                self, "risk_amount", decimal_value(self.risk_amount, "risk_amount")
            )
        if self.source_timestamp is not None:
            timestamp = self.source_timestamp
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("source_timestamp is invalid")
            object.__setattr__(self, "source_timestamp", timestamp.astimezone(UTC))
        object.__setattr__(self, "reason_codes", reasons)

    def to_dict(self) -> dict[str, object]:
        return {
            "constraints_id": self.constraints_id,
            "decision_id": self.decision_id,
            "entry": None if self.entry is None else self.entry.to_dict(),
            "exchange": self.exchange,
            "intent_id": self.intent_id,
            "reason_codes": [item.value for item in self.reason_codes],
            "risk_amount": (
                None if self.risk_amount is None else decimal_text(self.risk_amount)
            ),
            "source_timestamp": (
                None
                if self.source_timestamp is None
                else self.source_timestamp.isoformat().replace("+00:00", "Z")
            ),
            "status": self.status.value,
            "stop_loss": (
                None if self.stop_loss is None else self.stop_loss.to_dict()
            ),
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "symbol": self.symbol,
            "take_profit": (
                None if self.take_profit is None else self.take_profit.to_dict()
            ),
            "timeframe": self.timeframe,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        )

    @staticmethod
    def stable_id(values: dict[str, object]) -> str:
        payload = json.dumps(
            values, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        return hashlib.sha256(payload.encode()).hexdigest()


__all__ = (
    "AccountExecutionSnapshot",
    "ApprovedRiskSnapshot",
    "ExecutionIntent",
    "ExecutionPolicy",
    "InstrumentConstraints",
    "IntentOrderType",
    "IntentReason",
    "IntentSide",
    "IntentStatus",
    "IntentTimeInForce",
    "OrderSpecification",
    "decimal_text",
    "decimal_value",
)
