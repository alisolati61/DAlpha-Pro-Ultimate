"""Fail-closed domain boundary for one manual BingX VST Demo canary."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import (
    ROUND_CEILING,
    ROUND_FLOOR,
    Decimal,
    InvalidOperation,
    localcontext,
)
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from src.exchange.models import BingXBalance, BingXPosition
from src.execution_intent.models import (
    ExecutionIntent,
    IntentOrderType,
    IntentReason,
    IntentSide,
    IntentStatus,
    IntentTimeInForce,
    OrderSpecification,
)

from .models import (
    VST_BASE_URLS,
    KillSwitchState,
    ReconciliationResult,
    ReconciliationState,
    RemoteOrder,
    RemoteOrderStatus,
    canonical,
)

Clock = Callable[[], int]


class DemoOrderStatus(str, Enum):
    DRY_RUN_READY = "DRY_RUN_READY"
    SUBMITTED = "SUBMITTED"
    CANCELLED = "CANCELLED"
    RECONCILED = "RECONCILED"
    AMBIGUOUS = "AMBIGUOUS"
    UNEXPECTED_FILL = "UNEXPECTED_FILL"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class DemoCanaryError(Exception):
    """Stable public failure carrying no remote or credential detail."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class DemoAmbiguousSubmission(DemoCanaryError):
    def __init__(self) -> None:
        super().__init__("ambiguous_submission")


@dataclass(frozen=True, slots=True)
class DemoCanaryPolicy:
    """Non-configurable upper bounds for the first controlled Demo write."""

    maximum_notional: Decimal = Decimal("10")
    maximum_leverage: int = 2
    intent_ttl_ms: int = 300_000
    future_tolerance_ms: int = 5_000
    version: str = "bingx-vst-demo-canary-v1"

    def __post_init__(self) -> None:
        if (
            not self.maximum_notional.is_finite()
            or self.maximum_notional <= 0
            or isinstance(self.maximum_leverage, bool)
            or self.maximum_leverage < 1
            or isinstance(self.intent_ttl_ms, bool)
            or self.intent_ttl_ms < 1
            or isinstance(self.future_tolerance_ms, bool)
            or self.future_tolerance_ms < 0
            or not self.version.strip()
        ):
            raise ValueError("demo canary policy is invalid")

    @property
    def policy_id(self) -> str:
        payload = canonical(
            {
                "future_tolerance_ms": self.future_tolerance_ms,
                "intent_ttl_ms": self.intent_ttl_ms,
                "maximum_leverage": self.maximum_leverage,
                "maximum_notional": self.maximum_notional,
                "version": self.version,
            }
        )
        return hashlib.sha256(payload.encode()).hexdigest()


DEFAULT_DEMO_CANARY_POLICY = DemoCanaryPolicy()

_PASSIVE_BUFFER_BPS = Decimal("1")
_PASSIVE_STOP_FRACTION = Decimal("0.25")
_MIN_PASSIVE_BUFFER_TICKS = Decimal("2")


@dataclass(frozen=True, slots=True)
class DemoContractConstraints:
    symbol: str
    price_tick: Decimal
    quantity_step: Decimal
    minimum_quantity: Decimal
    minimum_notional: Decimal
    maximum_long_leverage: int
    maximum_short_leverage: int
    trading_enabled: bool
    snapshot_id: str = ""

    def __post_init__(self) -> None:
        if (
            not self.symbol.strip()
            or not isinstance(self.trading_enabled, bool)
        ):
            raise ValueError("contract constraints are invalid")
        for field_name in (
            "price_tick",
            "quantity_step",
            "minimum_quantity",
            "minimum_notional",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
                raise ValueError("contract constraints are invalid")
        for field_name in ("maximum_long_leverage", "maximum_short_leverage"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("contract constraints are invalid")
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        expected = hashlib.sha256(
            canonical(self.to_dict(include_snapshot_id=False)).encode()
        ).hexdigest()
        if self.snapshot_id and not hmac.compare_digest(self.snapshot_id, expected):
            raise ValueError("contract snapshot digest is invalid")
        object.__setattr__(self, "snapshot_id", expected)

    def to_dict(self, *, include_snapshot_id: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "maximum_long_leverage": self.maximum_long_leverage,
            "maximum_short_leverage": self.maximum_short_leverage,
            "minimum_notional": self.minimum_notional,
            "minimum_quantity": self.minimum_quantity,
            "price_tick": self.price_tick,
            "quantity_step": self.quantity_step,
            "symbol": self.symbol,
            "trading_enabled": self.trading_enabled,
        }
        if include_snapshot_id:
            value["snapshot_id"] = self.snapshot_id
        return value


@dataclass(frozen=True, slots=True)
class DemoTopOfBook:
    symbol: str
    best_bid: Decimal
    best_ask: Decimal
    update_id: str

    def __post_init__(self) -> None:
        if not self.symbol.strip() or not self.update_id.strip():
            raise ValueError("order book snapshot is invalid")
        if (
            not self.best_bid.is_finite()
            or not self.best_ask.is_finite()
            or self.best_bid <= 0
            or self.best_ask <= self.best_bid
        ):
            raise ValueError("order book snapshot is invalid")
        object.__setattr__(self, "symbol", self.symbol.strip().upper())


@dataclass(frozen=True, slots=True)
class DemoLeverageSnapshot:
    symbol: str
    long_leverage: int
    short_leverage: int

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("leverage snapshot is invalid")
        for field_name in ("long_leverage", "short_leverage"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("leverage snapshot is invalid")
        object.__setattr__(self, "symbol", self.symbol.strip().upper())


@dataclass(frozen=True, slots=True)
class DemoOrderPlan:
    intent_id: str
    intent_digest: str
    policy_id: str
    constraints_snapshot_id: str
    account_snapshot_id: str
    market_snapshot_id: str
    symbol: str
    side: str
    position_side: str
    order_type: str
    time_in_force: str
    quantity: Decimal
    limit_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    notional: Decimal
    leverage: int
    client_order_id: str
    selected_host: str
    expires_at_ms: int
    planned_lifecycle_actions: tuple[str, ...]
    digest: str = ""

    def __post_init__(self) -> None:
        text_fields = (
            "intent_id",
            "intent_digest",
            "policy_id",
            "constraints_snapshot_id",
            "account_snapshot_id",
            "market_snapshot_id",
            "symbol",
            "side",
            "position_side",
            "order_type",
            "time_in_force",
            "client_order_id",
            "selected_host",
        )
        if any(not str(getattr(self, name)).strip() for name in text_fields):
            raise ValueError("demo order plan is invalid")
        if not self.planned_lifecycle_actions:
            raise ValueError("demo order plan is invalid")
        if self.planned_lifecycle_actions != (
            "submit_protected_limit_once",
            "query_by_client_order_id",
            "cancel_once_if_open",
            "query_final_state",
            "reconcile_authoritative_state",
        ):
            raise ValueError("demo order plan lifecycle is invalid")
        for field_name in (
            "quantity",
            "limit_price",
            "stop_loss",
            "take_profit",
            "notional",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
                raise ValueError("demo order plan is invalid")
        if self.notional != self.quantity * self.limit_price:
            raise ValueError("demo order plan notional is invalid")
        if self.order_type != "LIMIT" or self.time_in_force != "PostOnly":
            raise ValueError("demo order plan type is invalid")
        if self.side not in {"BUY", "SELL"}:
            raise ValueError("demo order plan side is invalid")
        if self.position_side not in {"BOTH", "LONG", "SHORT"}:
            raise ValueError("demo order plan position side is invalid")
        if (
            (self.side == "BUY" and self.position_side == "SHORT")
            or (self.side == "SELL" and self.position_side == "LONG")
        ):
            raise ValueError("demo order plan position side is invalid")
        if self.side == "BUY" and not (
            self.stop_loss < self.limit_price < self.take_profit
        ):
            raise ValueError("demo order plan protection is invalid")
        if self.side == "SELL" and not (
            self.take_profit < self.limit_price < self.stop_loss
        ):
            raise ValueError("demo order plan protection is invalid")
        if self.selected_host.rstrip("/") not in VST_BASE_URLS:
            raise ValueError("demo order plan host is invalid")
        if (
            isinstance(self.leverage, bool)
            or not isinstance(self.leverage, int)
            or self.leverage < 1
            or self.leverage > DEFAULT_DEMO_CANARY_POLICY.maximum_leverage
            or self.notional > DEFAULT_DEMO_CANARY_POLICY.maximum_notional
            or isinstance(self.expires_at_ms, bool)
            or not isinstance(self.expires_at_ms, int)
            or self.expires_at_ms < 1
        ):
            raise ValueError("demo order plan bounds are invalid")
        if not self.client_order_id.isalnum() or len(self.client_order_id) > 40:
            raise ValueError("demo client order id is invalid")
        expected_client_id = (
            "dalphavst"
            + hashlib.sha256(
                f"bingx-vst:{self.intent_id}".encode()
            ).hexdigest()[:24]
        )
        if self.client_order_id != expected_client_id:
            raise ValueError("demo client order id is invalid")
        if any(
            not _is_sha256(getattr(self, field_name))
            for field_name in (
                "intent_digest",
                "policy_id",
                "constraints_snapshot_id",
                "account_snapshot_id",
                "market_snapshot_id",
            )
        ):
            raise ValueError("demo order plan digest field is invalid")
        expected = hashlib.sha256(
            self.to_json(include_digest=False).encode()
        ).hexdigest()
        if self.digest and not hmac.compare_digest(self.digest, expected):
            raise ValueError("demo order plan digest is invalid")
        object.__setattr__(self, "digest", expected)

    def to_dict(self, *, include_digest: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "account_snapshot_id": self.account_snapshot_id,
            "client_order_id": self.client_order_id,
            "constraints_snapshot_id": self.constraints_snapshot_id,
            "expires_at_ms": self.expires_at_ms,
            "intent_digest": self.intent_digest,
            "intent_id": self.intent_id,
            "leverage": self.leverage,
            "limit_price": self.limit_price,
            "market_snapshot_id": self.market_snapshot_id,
            "notional": self.notional,
            "order_type": self.order_type,
            "planned_lifecycle_actions": self.planned_lifecycle_actions,
            "policy_id": self.policy_id,
            "position_side": self.position_side,
            "quantity": self.quantity,
            "selected_host": self.selected_host,
            "side": self.side,
            "stop_loss": self.stop_loss,
            "symbol": self.symbol,
            "take_profit": self.take_profit,
            "time_in_force": self.time_in_force,
        }
        if include_digest:
            value["digest"] = self.digest
        return value

    def to_json(self, *, include_digest: bool = True) -> str:
        return canonical(self.to_dict(include_digest=include_digest))


@dataclass(frozen=True, slots=True)
class DemoOrderReport:
    status: DemoOrderStatus
    transitions: tuple[DemoOrderStatus, ...]
    plan: DemoOrderPlan | None
    selected_host: str | None
    client_order_id: str | None
    order_id: str | None
    remote_status: str | None
    filled_quantity: Decimal
    reconciliation: ReconciliationResult
    kill_switch: KillSwitchState
    reason_codes: tuple[str, ...]
    recommended_actions: tuple[str, ...]
    reported_at_ms: int
    digest: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.status, DemoOrderStatus) or any(
            not isinstance(item, DemoOrderStatus) for item in self.transitions
        ):
            raise ValueError("demo order report status is invalid")
        if not self.transitions or self.transitions[-1] is not self.status:
            raise ValueError("demo order report transitions are invalid")
        if self.plan is not None and not isinstance(self.plan, DemoOrderPlan):
            raise ValueError("demo order report plan is invalid")
        if not isinstance(self.reconciliation, ReconciliationResult):
            raise ValueError("demo order report reconciliation is invalid")
        if not isinstance(self.kill_switch, KillSwitchState):
            raise ValueError("demo order report kill switch is invalid")
        if self.plan is not None and (
            self.selected_host != self.plan.selected_host
            or self.client_order_id != self.plan.client_order_id
        ):
            raise ValueError("demo order report identity is invalid")
        object.__setattr__(self, "reason_codes", tuple(sorted(set(self.reason_codes))))
        object.__setattr__(
            self,
            "recommended_actions",
            tuple(sorted(set(self.recommended_actions))),
        )
        if not isinstance(self.filled_quantity, Decimal):
            object.__setattr__(
                self,
                "filled_quantity",
                Decimal(str(self.filled_quantity)),
            )
        if (
            not self.filled_quantity.is_finite()
            or self.filled_quantity < 0
            or isinstance(self.reported_at_ms, bool)
            or not isinstance(self.reported_at_ms, int)
            or self.reported_at_ms < 0
        ):
            raise ValueError("demo order report is invalid")
        expected = hashlib.sha256(
            self.to_json(include_digest=False).encode()
        ).hexdigest()
        if self.digest and not hmac.compare_digest(self.digest, expected):
            raise ValueError("demo order report digest is invalid")
        object.__setattr__(self, "digest", expected)

    def to_dict(self, *, include_digest: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "client_order_id": self.client_order_id,
            "filled_quantity": self.filled_quantity,
            "kill_switch": {
                "active": self.kill_switch.active,
                "reason_codes": self.kill_switch.reason_codes,
            },
            "order_id": self.order_id,
            "plan": None if self.plan is None else self.plan.to_dict(),
            "reason_codes": self.reason_codes,
            "recommended_actions": self.recommended_actions,
            "reconciliation": {
                "reason_codes": self.reconciliation.reason_codes,
                "recommended_actions": self.reconciliation.recommended_actions,
                "state": self.reconciliation.state.value,
            },
            "remote_status": self.remote_status,
            "reported_at_ms": self.reported_at_ms,
            "selected_host": self.selected_host,
            "status": self.status.value,
            "transitions": tuple(item.value for item in self.transitions),
        }
        if include_digest:
            value["digest"] = self.digest
        return value

    def to_json(self, *, include_digest: bool = True) -> str:
        return canonical(self.to_dict(include_digest=include_digest))


@runtime_checkable
class AsyncDemoOrderTransport(Protocol):
    """The complete exchange surface reachable by the Demo canary."""

    async def fetch_constraints(self, symbol: str) -> DemoContractConstraints: ...

    async def fetch_orderbook(self, symbol: str) -> DemoTopOfBook: ...

    async def fetch_balances(self) -> Sequence[BingXBalance]: ...

    async def fetch_positions(self, symbol: str) -> Sequence[BingXPosition]: ...

    async def fetch_leverage(self, symbol: str) -> DemoLeverageSnapshot: ...

    async def fetch_position_mode(self) -> str: ...

    async def fetch_open_orders(self, symbol: str) -> Sequence[RemoteOrder]: ...

    async def fetch_recent_orders(self, symbol: str) -> Sequence[RemoteOrder]: ...

    async def submit_protected_limit(self, plan: DemoOrderPlan) -> RemoteOrder: ...

    async def query_order(
        self, symbol: str, client_order_id: str
    ) -> RemoteOrder | None: ...

    async def cancel_order(
        self, symbol: str, client_order_id: str
    ) -> RemoteOrder | None: ...

    async def close(self) -> None: ...

    @property
    def selected_host(self) -> str: ...


def load_canonical_ready_intent(
    serialized: str,
    expected_digest: str,
) -> tuple[ExecutionIntent, str]:
    """Load only the frozen model's exact canonical READY representation."""

    if not isinstance(serialized, str) or not isinstance(expected_digest, str):
        raise DemoCanaryError("invalid_intent_contract")
    normalized = serialized.strip()
    actual_digest = hashlib.sha256(normalized.encode()).hexdigest()
    if not hmac.compare_digest(actual_digest, expected_digest.strip().casefold()):
        raise DemoCanaryError("intent_digest_mismatch")
    try:
        payload = json.loads(normalized)
        if not isinstance(payload, dict):
            raise ValueError
        if payload.get("status") != IntentStatus.READY.value:
            raise DemoCanaryError("intent_not_ready")
        expected_fields = {
            "constraints_id",
            "decision_id",
            "entry",
            "exchange",
            "intent_id",
            "reason_codes",
            "risk_amount",
            "source_timestamp",
            "status",
            "stop_loss",
            "strategy_id",
            "strategy_version",
            "symbol",
            "take_profit",
            "timeframe",
        }
        if set(payload) != expected_fields:
            raise ValueError
        intent = ExecutionIntent(
            intent_id=_required_string(payload["intent_id"]),
            decision_id=_required_string(payload["decision_id"]),
            status=IntentStatus(payload["status"]),
            symbol=_required_string(payload["symbol"]),
            exchange=_required_string(payload["exchange"]),
            timeframe=_required_string(payload["timeframe"]),
            entry=_parse_order_specification(payload["entry"]),
            stop_loss=_parse_order_specification(payload["stop_loss"]),
            take_profit=_parse_order_specification(payload["take_profit"]),
            strategy_id=_required_string(payload["strategy_id"]),
            strategy_version=_required_string(payload["strategy_version"]),
            risk_amount=Decimal(_required_string(payload["risk_amount"])),
            constraints_id=_required_string(payload["constraints_id"]),
            source_timestamp=_parse_timestamp(payload["source_timestamp"]),
            reason_codes=tuple(IntentReason(item) for item in payload["reason_codes"]),
        )
    except DemoCanaryError:
        raise
    except (InvalidOperation, KeyError, OverflowError, TypeError, ValueError):
        raise DemoCanaryError("invalid_intent_contract") from None
    if intent.to_json() != normalized:
        raise DemoCanaryError("intent_not_canonical")
    return intent, actual_digest


_PLAN_TEXT_FIELDS = (
    "intent_id",
    "intent_digest",
    "policy_id",
    "constraints_snapshot_id",
    "account_snapshot_id",
    "market_snapshot_id",
    "symbol",
    "side",
    "position_side",
    "order_type",
    "time_in_force",
    "client_order_id",
    "selected_host",
    "digest",
)
_PLAN_DECIMAL_FIELDS = (
    "quantity",
    "limit_price",
    "stop_loss",
    "take_profit",
    "notional",
)
_PLAN_INT_FIELDS = ("leverage", "expires_at_ms")
_PLAN_FIELDS = frozenset(
    _PLAN_TEXT_FIELDS + _PLAN_DECIMAL_FIELDS + _PLAN_INT_FIELDS
    + ("planned_lifecycle_actions",)
)


def load_canonical_demo_order_plan(serialized: str) -> DemoOrderPlan:
    """Load only the frozen model's exact canonical persisted ``DemoOrderPlan``.

    This performs no network or write operation. ``DemoOrderPlan.__post_init__``
    always recomputes the digest from the parsed fields and compares it to the
    embedded one with ``hmac.compare_digest``; requiring the embedded digest to
    already look like a sha256 hex string here closes the one path (a blank or
    absent digest) that would otherwise skip that comparison.
    """

    if not isinstance(serialized, str):
        raise DemoCanaryError("invalid_plan_schema")
    normalized = serialized.strip()
    try:
        payload = json.loads(normalized)
    except (TypeError, ValueError, json.JSONDecodeError):
        raise DemoCanaryError("invalid_plan_schema") from None
    if not isinstance(payload, dict) or set(payload) != _PLAN_FIELDS:
        raise DemoCanaryError("invalid_plan_schema")
    try:
        kwargs: dict[str, object] = {}
        for name in _PLAN_TEXT_FIELDS:
            value = payload[name]
            if not isinstance(value, str):
                raise ValueError
            kwargs[name] = value
        for name in _PLAN_INT_FIELDS:
            value = payload[name]
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError
            kwargs[name] = value
        for name in _PLAN_DECIMAL_FIELDS:
            value = payload[name]
            if not isinstance(value, str):
                raise ValueError
            kwargs[name] = Decimal(value)
        actions = payload["planned_lifecycle_actions"]
        if not isinstance(actions, list) or any(
            not isinstance(item, str) for item in actions
        ):
            raise ValueError
        kwargs["planned_lifecycle_actions"] = tuple(actions)
        if not _is_sha256(kwargs["digest"]):
            raise ValueError
        plan = DemoOrderPlan(**kwargs)  # type: ignore[arg-type]
    except ValueError as error:
        if str(error) == "demo order plan digest is invalid":
            raise DemoCanaryError("plan_artifact_digest_mismatch") from None
        raise DemoCanaryError("invalid_plan_schema") from None
    except (InvalidOperation, KeyError, OverflowError, TypeError):
        raise DemoCanaryError("invalid_plan_schema") from None
    if plan.to_json() != normalized:
        raise DemoCanaryError("invalid_plan_schema")
    return plan


def deterministic_client_order_id(intent_id: str) -> str:
    if not isinstance(intent_id, str) or not intent_id.strip():
        raise DemoCanaryError("invalid_intent_contract")
    digest = hashlib.sha256(f"bingx-vst:{intent_id.strip()}".encode()).hexdigest()
    return f"dalphavst{digest[:24]}"


def _passive_canary_limit_price(
    intent: ExecutionIntent,
    book: DemoTopOfBook,
    constraints: DemoContractConstraints,
) -> Decimal:
    """Derive a bounded maker-only canary price without increasing risk."""

    assert intent.entry is not None
    assert intent.stop_loss is not None
    assert intent.take_profit is not None

    entry = intent.entry
    stop = intent.stop_loss
    take = intent.take_profit
    tick = constraints.price_tick

    with localcontext() as context:
        context.prec = 50

        bps_buffer = (
            entry.price
            * _PASSIVE_BUFFER_BPS
            / Decimal("10000")
        )
        tick_buffer = tick * _MIN_PASSIVE_BUFFER_TICKS
        stop_distance = abs(
            entry.price - stop.price
        )
        stop_buffer_cap = (
            stop_distance * _PASSIVE_STOP_FRACTION
        )

        passive_buffer = max(
            tick_buffer,
            min(
                bps_buffer,
                stop_buffer_cap,
            ),
        )

        midpoint = (
            entry.price + stop.price
        ) / Decimal("2")

        if entry.side is IntentSide.BUY:
            raw_candidate = min(
                entry.price,
                book.best_ask - passive_buffer,
            )
            candidate = (
                raw_candidate / tick
            ).to_integral_value(
                rounding=ROUND_FLOOR
            ) * tick

            if (
                candidate <= 0
                or candidate < midpoint
                or candidate <= stop.price
                or candidate >= take.price
            ):
                raise DemoCanaryError(
                    "passive_limit_unavailable"
                )

            return candidate

        if entry.side is IntentSide.SELL:
            raw_candidate = max(
                entry.price,
                book.best_bid + passive_buffer,
            )
            candidate = (
                raw_candidate / tick
            ).to_integral_value(
                rounding=ROUND_CEILING
            ) * tick

            if (
                candidate <= 0
                or candidate > midpoint
                or candidate >= stop.price
                or candidate <= take.price
            ):
                raise DemoCanaryError(
                    "passive_limit_unavailable"
                )

            return candidate

    raise DemoCanaryError("passive_limit_unavailable")


async def build_demo_order_plan(
    intent: ExecutionIntent,
    intent_digest: str,
    transport: AsyncDemoOrderTransport,
    *,
    clock_ms: Clock,
    policy: DemoCanaryPolicy = DEFAULT_DEMO_CANARY_POLICY,
) -> DemoOrderPlan:
    """Validate an already approved intent against current authoritative reads."""

    _validate_intent(intent)
    canonical_digest = hashlib.sha256(intent.to_json().encode()).hexdigest()
    if not hmac.compare_digest(canonical_digest, intent_digest):
        raise DemoCanaryError("intent_digest_mismatch")
    assert intent.source_timestamp is not None
    source_ms = int(intent.source_timestamp.timestamp() * 1_000)
    now = clock_ms()
    if source_ms > now + policy.future_tolerance_ms:
        raise DemoCanaryError("intent_timestamp_invalid")
    expires_at = source_ms + policy.intent_ttl_ms
    if now > expires_at:
        raise DemoCanaryError("intent_expired")

    assert intent.symbol is not None
    assert intent.entry is not None
    assert intent.stop_loss is not None
    assert intent.take_profit is not None
    symbol = intent.symbol.upper()
    try:
        constraints = await transport.fetch_constraints(symbol)
        book = await transport.fetch_orderbook(symbol)
        balances = tuple(await transport.fetch_balances())
        positions = tuple(await transport.fetch_positions(symbol))
        leverage_snapshot = await transport.fetch_leverage(symbol)
        position_mode = await transport.fetch_position_mode()
        existing_order = await transport.query_order(
            symbol,
            deterministic_client_order_id(intent.intent_id),
        )
        open_orders = tuple(await transport.fetch_open_orders(symbol))
        recent_orders = tuple(await transport.fetch_recent_orders(symbol))
    except DemoCanaryError:
        raise
    except Exception:
        raise DemoCanaryError("canary_read_failed") from None
    if not isinstance(constraints, DemoContractConstraints):
        raise DemoCanaryError("constraints_snapshot_missing")
    if constraints.symbol != symbol or not constraints.trading_enabled:
        raise DemoCanaryError("unsupported_symbol")
    if not isinstance(book, DemoTopOfBook) or book.symbol != symbol:
        raise DemoCanaryError("invalid_orderbook_schema")
    if not balances or any(not isinstance(item, BingXBalance) for item in balances):
        raise DemoCanaryError("account_snapshot_missing")
    if any(not isinstance(item, BingXPosition) for item in positions):
        raise DemoCanaryError("positions_snapshot_invalid")
    if (
        not isinstance(leverage_snapshot, DemoLeverageSnapshot)
        or leverage_snapshot.symbol != symbol
    ):
        raise DemoCanaryError("invalid_leverage_schema")
    if position_mode not in {"HEDGE", "ONE_WAY"}:
        raise DemoCanaryError("invalid_position_mode_schema")
    if any(
        not isinstance(item, RemoteOrder)
        for item in (*open_orders, *recent_orders)
    ):
        raise DemoCanaryError("invalid_orders_snapshot")
    if existing_order is not None:
        if not isinstance(existing_order, RemoteOrder):
            raise DemoCanaryError("invalid_orders_snapshot")
        raise DemoCanaryError("duplicate_client_order_id")

    _validate_protection(intent)
    _validate_normalization(intent, constraints)
    entry = intent.entry
    side = entry.side.value
    position_side = (
        ("LONG" if entry.side is IntentSide.BUY else "SHORT")
        if position_mode == "HEDGE"
        else "BOTH"
    )
    if entry.side is IntentSide.BUY and entry.price >= book.best_ask:
        raise DemoCanaryError("marketable_limit_price")
    if entry.side is IntentSide.SELL and entry.price <= book.best_bid:
        raise DemoCanaryError("marketable_limit_price")

    limit_price = _passive_canary_limit_price(
        intent,
        book,
        constraints,
    )
    notional = entry.quantity * limit_price
    if entry.quantity < constraints.minimum_quantity:
        raise DemoCanaryError("quantity_below_exchange_minimum")
    if notional < constraints.minimum_notional:
        raise DemoCanaryError("notional_below_exchange_minimum")
    if notional > policy.maximum_notional:
        raise DemoCanaryError("demo_notional_cap_exceeded")
    leverage = (
        leverage_snapshot.long_leverage
        if entry.side is IntentSide.BUY
        else leverage_snapshot.short_leverage
    )
    exchange_cap = (
        constraints.maximum_long_leverage
        if entry.side is IntentSide.BUY
        else constraints.maximum_short_leverage
    )
    if leverage > policy.maximum_leverage or leverage > exchange_cap:
        raise DemoCanaryError("demo_leverage_cap_exceeded")
    vst_balances = tuple(item for item in balances if item.asset == "VST")
    settlement_balances = vst_balances or tuple(
        item for item in balances if item.asset == "USDT"
    )
    if not settlement_balances:
        raise DemoCanaryError("settlement_balance_missing")
    available = sum(
        (item.available_balance for item in settlement_balances),
        Decimal(0),
    )
    if available <= 0 or (notional / Decimal(leverage)) > available:
        raise DemoCanaryError("insufficient_available_margin")
    if any(
        item.symbol.upper() == symbol and item.position_amount != 0
        for item in positions
    ):
        raise DemoCanaryError("existing_symbol_position")

    client_order_id = deterministic_client_order_id(intent.intent_id)
    for order in (*open_orders, *recent_orders):
        if order.client_order_id == client_order_id:
            raise DemoCanaryError("duplicate_client_order_id")
    if any(
        order.symbol.upper() == symbol and not order.reduce_only
        for order in open_orders
    ):
        raise DemoCanaryError("existing_open_entry_order")

    account_snapshot_id = _digest(
        {
            "balances": sorted(
                (
                    {
                        "asset": item.asset,
                        "available_balance": item.available_balance,
                        "margin_balance": item.margin_balance,
                        "wallet_balance": item.wallet_balance,
                    }
                    for item in balances
                ),
                key=lambda item: str(item["asset"]),
            ),
            "leverage": leverage,
            "position_mode": position_mode,
            "positions": sorted(
                (
                    {
                        "amount": item.position_amount,
                        "leverage": item.leverage,
                        "side": item.position_side.value,
                        "symbol": item.symbol,
                    }
                    for item in positions
                ),
                key=lambda item: (str(item["symbol"]), str(item["side"])),
            ),
        }
    )
    market_snapshot_id = _digest(
        {
            "best_ask": book.best_ask,
            "best_bid": book.best_bid,
            "symbol": book.symbol,
        }
    )
    return DemoOrderPlan(
        intent_id=intent.intent_id,
        intent_digest=intent_digest,
        policy_id=policy.policy_id,
        constraints_snapshot_id=constraints.snapshot_id,
        account_snapshot_id=account_snapshot_id,
        market_snapshot_id=market_snapshot_id,
        symbol=symbol,
        side=side,
        position_side=position_side,
        order_type="LIMIT",
        time_in_force="PostOnly",
        quantity=entry.quantity,
        limit_price=limit_price,
        stop_loss=intent.stop_loss.price,
        take_profit=intent.take_profit.price,
        notional=notional,
        leverage=leverage,
        client_order_id=client_order_id,
        selected_host=transport.selected_host,
        expires_at_ms=expires_at,
        planned_lifecycle_actions=(
            "submit_protected_limit_once",
            "query_by_client_order_id",
            "cancel_once_if_open",
            "query_final_state",
            "reconcile_authoritative_state",
        ),
    )


async def execute_demo_order_plan(
    plan: DemoOrderPlan,
    transport: AsyncDemoOrderTransport,
    *,
    approved_plan_digest: str,
    typed_confirmation: str,
    clock_ms: Clock,
) -> DemoOrderReport:
    """Submit at most once and resolve the single canary by client ID."""

    if not hmac.compare_digest(plan.digest, approved_plan_digest.strip().casefold()):
        raise DemoCanaryError("plan_digest_mismatch")
    expected_confirmation = f"SUBMIT {plan.client_order_id}"
    if not hmac.compare_digest(typed_confirmation, expected_confirmation):
        raise DemoCanaryError("typed_confirmation_mismatch")
    if clock_ms() > plan.expires_at_ms:
        raise DemoCanaryError("plan_expired")

    try:
        current_constraints = await transport.fetch_constraints(plan.symbol)
        current_positions = tuple(
            await transport.fetch_positions(plan.symbol)
        )
        current_leverage = await transport.fetch_leverage(plan.symbol)
        current_position_mode = await transport.fetch_position_mode()
        current_open_orders = tuple(
            await transport.fetch_open_orders(plan.symbol)
        )
        # Keep the public book sample closest to the sole write.
        current_book = await transport.fetch_orderbook(plan.symbol)
    except DemoCanaryError:
        raise
    except Exception:
        raise DemoCanaryError("pre_submit_validation_failed") from None
    if (
        not isinstance(current_constraints, DemoContractConstraints)
        or current_constraints.symbol != plan.symbol
        or not current_constraints.trading_enabled
    ):
        raise DemoCanaryError("constraints_snapshot_missing")
    if current_constraints.snapshot_id != plan.constraints_snapshot_id:
        raise DemoCanaryError("constraints_snapshot_changed")
    if plan.quantity % current_constraints.quantity_step != 0 or any(
        price % current_constraints.price_tick != 0
        for price in (plan.limit_price, plan.stop_loss, plan.take_profit)
    ):
        raise DemoCanaryError("order_not_exchange_normalized")
    if (
        plan.quantity < current_constraints.minimum_quantity
        or plan.notional < current_constraints.minimum_notional
    ):
        raise DemoCanaryError("order_below_exchange_minimum")
    if (
        not isinstance(current_book, DemoTopOfBook)
        or current_book.symbol != plan.symbol
    ):
        raise DemoCanaryError("invalid_orderbook_schema")
    if plan.side == "BUY" and plan.limit_price >= current_book.best_ask:
        raise DemoCanaryError("marketable_limit_price")
    if plan.side == "SELL" and plan.limit_price <= current_book.best_bid:
        raise DemoCanaryError("marketable_limit_price")
    if any(not isinstance(item, BingXPosition) for item in current_positions):
        raise DemoCanaryError("positions_snapshot_invalid")
    if any(
        item.symbol.upper() == plan.symbol and item.position_amount != 0
        for item in current_positions
    ):
        raise DemoCanaryError("existing_symbol_position")
    if (
        not isinstance(current_leverage, DemoLeverageSnapshot)
        or current_leverage.symbol != plan.symbol
    ):
        raise DemoCanaryError("invalid_leverage_schema")
    selected_leverage = (
        current_leverage.long_leverage
        if plan.side == "BUY"
        else current_leverage.short_leverage
    )
    exchange_leverage_cap = (
        current_constraints.maximum_long_leverage
        if plan.side == "BUY"
        else current_constraints.maximum_short_leverage
    )
    if (
        selected_leverage != plan.leverage
        or selected_leverage > DEFAULT_DEMO_CANARY_POLICY.maximum_leverage
        or selected_leverage > exchange_leverage_cap
    ):
        raise DemoCanaryError("pre_submit_leverage_changed")
    expected_position_side = (
        ("LONG" if plan.side == "BUY" else "SHORT")
        if current_position_mode == "HEDGE"
        else "BOTH" if current_position_mode == "ONE_WAY" else None
    )
    if expected_position_side != plan.position_side:
        raise DemoCanaryError("pre_submit_position_mode_changed")
    if any(not isinstance(item, RemoteOrder) for item in current_open_orders):
        raise DemoCanaryError("invalid_orders_snapshot")
    if any(
        item.symbol.upper() == plan.symbol and not item.reduce_only
        for item in current_open_orders
    ):
        raise DemoCanaryError("existing_open_entry_order")
    try:
        existing_order = await transport.query_order(
            plan.symbol,
            plan.client_order_id,
        )
    except DemoCanaryError:
        raise
    except Exception:
        raise DemoCanaryError("pre_submit_validation_failed") from None
    if existing_order is not None:
        if not isinstance(existing_order, RemoteOrder):
            raise DemoCanaryError("invalid_orders_snapshot")
        raise DemoCanaryError("duplicate_client_order_id")
    if clock_ms() > plan.expires_at_ms:
        raise DemoCanaryError("plan_expired")

    transitions: list[DemoOrderStatus] = []
    order: RemoteOrder | None = None
    submit_ambiguous = False
    try:
        order = await transport.submit_protected_limit(plan)
        transitions.append(DemoOrderStatus.SUBMITTED)
    except DemoAmbiguousSubmission:
        submit_ambiguous = True
    except DemoCanaryError as error:
        return _execution_report(
            DemoOrderStatus.FAILED,
            transitions,
            plan,
            None,
            (error.reason_code,),
            ("inspect_vst_account",),
            clock_ms(),
            kill=True,
        )
    except Exception:
        # An untyped failure at the write boundary cannot prove that dispatch
        # did not occur. Treat it exactly like any other ambiguous submit.
        submit_ambiguous = True

    try:
        authoritative = await transport.query_order(plan.symbol, plan.client_order_id)
    except Exception:
        authoritative = None
    if authoritative is None:
        reason = (
            "ambiguous_submission_unresolved"
            if submit_ambiguous
            else "submitted_order_unavailable"
        )
        return _execution_report(
            DemoOrderStatus.AMBIGUOUS,
            transitions,
            plan,
            order,
            (reason,),
            ("inspect_vst_account", "do_not_resubmit"),
            clock_ms(),
            kill=True,
        )
    if not isinstance(authoritative, RemoteOrder):
        return _execution_report(
            DemoOrderStatus.FAILED,
            transitions,
            plan,
            None,
            ("invalid_order_response_schema",),
            ("inspect_vst_account", "do_not_resubmit"),
            clock_ms(),
            kill=True,
        )
    order = authoritative
    if not transitions:
        transitions.append(DemoOrderStatus.SUBMITTED)
    if not _order_matches_plan(order, plan):
        return _execution_report(
            DemoOrderStatus.FAILED,
            transitions,
            plan,
            order,
            ("remote_order_identity_mismatch",),
            ("inspect_vst_account", "do_not_resubmit"),
            clock_ms(),
            kill=True,
        )

    open_statuses = {RemoteOrderStatus.NEW, RemoteOrderStatus.PARTIALLY_FILLED}
    if order.status in open_statuses:
        try:
            await transport.cancel_order(plan.symbol, plan.client_order_id)
        except Exception:
            pass
        try:
            final_order = await transport.query_order(
                plan.symbol, plan.client_order_id
            )
        except Exception:
            final_order = None
        if final_order is None:
            return _execution_report(
                DemoOrderStatus.AMBIGUOUS,
                transitions,
                plan,
                order,
                ("cancel_outcome_ambiguous",),
                ("inspect_vst_account", "do_not_resubmit"),
                clock_ms(),
                kill=True,
            )
        if not isinstance(final_order, RemoteOrder) or not _order_matches_plan(
            final_order, plan
        ):
            return _execution_report(
                DemoOrderStatus.FAILED,
                transitions,
                plan,
                None,
                ("remote_order_identity_mismatch",),
                ("inspect_vst_account", "do_not_resubmit"),
                clock_ms(),
                kill=True,
            )
        order = final_order
        if order.status is RemoteOrderStatus.CANCELED:
            transitions.append(DemoOrderStatus.CANCELLED)

    try:
        positions = tuple(await transport.fetch_positions(plan.symbol))
        open_orders = tuple(await transport.fetch_open_orders(plan.symbol))
    except Exception:
        return _execution_report(
            DemoOrderStatus.AMBIGUOUS,
            transitions,
            plan,
            order,
            ("reconciliation_reads_unavailable",),
            ("retry_read_only_reconciliation", "do_not_resubmit"),
            clock_ms(),
            kill=True,
        )

    if any(not isinstance(item, BingXPosition) for item in positions) or any(
        not isinstance(item, RemoteOrder) for item in open_orders
    ):
        return _execution_report(
            DemoOrderStatus.AMBIGUOUS,
            transitions,
            plan,
            order,
            ("invalid_reconciliation_schema",),
            ("retry_read_only_reconciliation", "do_not_resubmit"),
            clock_ms(),
            kill=True,
        )

    matching_open_orders = tuple(
        item
        for item in open_orders
        if item.client_order_id == plan.client_order_id
    )
    unexpected_position = any(
        item.symbol.upper() == plan.symbol and item.position_amount != 0
        for item in positions
    )
    if (
        order.filled_quantity > 0
        or any(item.filled_quantity > 0 for item in matching_open_orders)
        or unexpected_position
        or order.status
        in {
            RemoteOrderStatus.FILLED,
            RemoteOrderStatus.PARTIALLY_FILLED,
        }
    ):
        return _execution_report(
            DemoOrderStatus.UNEXPECTED_FILL,
            transitions,
            plan,
            order,
            ("unexpected_canary_fill",),
            ("operator_recovery_required", "inspect_vst_account"),
            clock_ms(),
            kill=True,
            reconciliation=ReconciliationResult(
                ReconciliationState.MISMATCH,
                ("unexpected_canary_fill",),
                ("activate_kill_switch", "inspect_remote_account"),
            ),
        )
    # Presence in the authoritative open-orders endpoint wins over an
    # inconsistent or unrecognized item status.
    still_open = bool(matching_open_orders)
    if still_open or order.status in open_statuses:
        return _execution_report(
            DemoOrderStatus.AMBIGUOUS,
            transitions,
            plan,
            order,
            ("canary_order_still_open",),
            ("inspect_vst_account", "do_not_resubmit"),
            clock_ms(),
            kill=True,
        )
    if order.status not in {
        RemoteOrderStatus.CANCELED,
        RemoteOrderStatus.EXPIRED,
        RemoteOrderStatus.REJECTED,
    }:
        return _execution_report(
            DemoOrderStatus.AMBIGUOUS,
            transitions,
            plan,
            order,
            ("remote_order_state_unknown",),
            ("inspect_vst_account", "do_not_resubmit"),
            clock_ms(),
            kill=True,
        )
    transitions.append(DemoOrderStatus.RECONCILED)
    return _execution_report(
        DemoOrderStatus.RECONCILED,
        transitions,
        plan,
        order,
        ("reconciled",),
        ("no_action",),
        clock_ms(),
        kill=False,
        reconciliation=ReconciliationResult(
            ReconciliationState.MATCHED,
            ("matched",),
            ("no_action",),
        ),
    )


def dry_run_report(plan: DemoOrderPlan, *, reported_at_ms: int) -> DemoOrderReport:
    return _execution_report(
        DemoOrderStatus.DRY_RUN_READY,
        (DemoOrderStatus.DRY_RUN_READY,),
        plan,
        None,
        ("dry_run_ready",),
        ("review_plan",),
        reported_at_ms,
        kill=False,
    )


def blocked_report(
    reason_code: str,
    *,
    reported_at_ms: int,
    plan: DemoOrderPlan | None = None,
) -> DemoOrderReport:
    return _execution_report(
        DemoOrderStatus.BLOCKED,
        (DemoOrderStatus.BLOCKED,),
        plan,
        None,
        (reason_code,),
        ("correct_prerequisite_and_restart",),
        reported_at_ms,
        kill=False,
    )


def failed_report(
    reason_code: str,
    *,
    reported_at_ms: int,
    plan: DemoOrderPlan | None = None,
) -> DemoOrderReport:
    return _execution_report(
        DemoOrderStatus.FAILED,
        (DemoOrderStatus.FAILED,),
        plan,
        None,
        (reason_code,),
        ("inspect_vst_account",),
        reported_at_ms,
        kill=True,
    )


def _execution_report(
    status: DemoOrderStatus,
    transitions: Sequence[DemoOrderStatus],
    plan: DemoOrderPlan | None,
    order: RemoteOrder | None,
    reasons: tuple[str, ...],
    actions: tuple[str, ...],
    reported_at_ms: int,
    *,
    kill: bool,
    reconciliation: ReconciliationResult | None = None,
) -> DemoOrderReport:
    if reconciliation is None:
        reconciliation = ReconciliationResult(
            ReconciliationState.UNKNOWN,
            ("not_reconciled",),
            ("fetch_authoritative_state",),
        )
    normalized_transitions = list(transitions)
    if not normalized_transitions or normalized_transitions[-1] is not status:
        normalized_transitions.append(status)
    return DemoOrderReport(
        status=status,
        transitions=tuple(normalized_transitions),
        plan=plan,
        selected_host=(plan.selected_host if plan else None),
        client_order_id=(plan.client_order_id if plan else None),
        order_id=(order.order_id if order else None),
        remote_status=(order.status.value if order else None),
        filled_quantity=(order.filled_quantity if order else Decimal(0)),
        reconciliation=reconciliation,
        kill_switch=KillSwitchState(kill, reasons if kill else ()),
        reason_codes=reasons,
        recommended_actions=actions,
        reported_at_ms=reported_at_ms,
    )


def _validate_intent(intent: ExecutionIntent) -> None:
    if not isinstance(intent, ExecutionIntent):
        raise DemoCanaryError("invalid_intent_contract")
    if intent.status is not IntentStatus.READY:
        raise DemoCanaryError("intent_not_ready")
    if intent.reason_codes != (IntentReason.INTENT_READY,):
        raise DemoCanaryError("intent_not_ready")
    if intent.exchange is None or intent.exchange.casefold() != "bingx":
        raise DemoCanaryError("unsupported_exchange")
    if intent.entry is None or intent.entry.order_type is not IntentOrderType.LIMIT:
        raise DemoCanaryError("unsupported_order_type")
    if intent.entry.time_in_force is not IntentTimeInForce.GTC:
        raise DemoCanaryError("unsupported_time_in_force")
    if intent.entry.reduce_only:
        raise DemoCanaryError("entry_must_not_reduce_only")
    if not intent.constraints_id:
        raise DemoCanaryError("constraints_snapshot_missing")


def _validate_protection(intent: ExecutionIntent) -> None:
    entry = intent.entry
    stop = intent.stop_loss
    take = intent.take_profit
    if entry is None or stop is None or take is None:
        raise DemoCanaryError("protected_order_required")
    if (
        stop.order_type is not IntentOrderType.STOP
        or take.order_type is not IntentOrderType.TAKE_PROFIT
        or not stop.reduce_only
        or not take.reduce_only
        or stop.quantity != entry.quantity
        or take.quantity != entry.quantity
        or stop.side is entry.side
        or take.side is entry.side
    ):
        raise DemoCanaryError("invalid_protection_contract")
    if entry.side is IntentSide.BUY and not (stop.price < entry.price < take.price):
        raise DemoCanaryError("invalid_protection_prices")
    if entry.side is IntentSide.SELL and not (take.price < entry.price < stop.price):
        raise DemoCanaryError("invalid_protection_prices")


def _validate_normalization(
    intent: ExecutionIntent,
    constraints: DemoContractConstraints,
) -> None:
    assert intent.entry is not None
    assert intent.stop_loss is not None
    assert intent.take_profit is not None
    if intent.entry.quantity % constraints.quantity_step != 0:
        raise DemoCanaryError("quantity_not_exchange_normalized")
    for price in (
        intent.entry.price,
        intent.stop_loss.price,
        intent.take_profit.price,
    ):
        if price % constraints.price_tick != 0:
            raise DemoCanaryError("price_not_exchange_normalized")


def _order_matches_plan(order: RemoteOrder, plan: DemoOrderPlan) -> bool:
    return (
        order.client_order_id == plan.client_order_id
        and order.symbol.upper() == plan.symbol
        and order.side.upper() == plan.side
        and order.order_type.upper() == "LIMIT"
        and not order.reduce_only
        and order.original_quantity == plan.quantity
        and order.price == plan.limit_price
    )


def _parse_order_specification(value: object) -> OrderSpecification:
    if not isinstance(value, Mapping):
        raise ValueError
    if set(value) != {
        "order_type",
        "price",
        "quantity",
        "reduce_only",
        "side",
        "time_in_force",
    }:
        raise ValueError
    reduce_only = value["reduce_only"]
    if not isinstance(reduce_only, bool):
        raise ValueError
    return OrderSpecification(
        side=IntentSide(value["side"]),
        order_type=IntentOrderType(value["order_type"]),
        price=Decimal(_required_string(value["price"])),
        quantity=Decimal(_required_string(value["quantity"])),
        time_in_force=IntentTimeInForce(value["time_in_force"]),
        reduce_only=reduce_only,
    )


def _parse_timestamp(value: object) -> datetime:
    text = _required_string(value)
    if not text.endswith("Z"):
        raise ValueError
    parsed = datetime.fromisoformat(f"{text[:-1]}+00:00")
    if parsed.tzinfo is None:
        raise ValueError
    return parsed.astimezone(UTC)


def _required_string(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError
    return value


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


__all__ = (
    "AsyncDemoOrderTransport",
    "DemoAmbiguousSubmission",
    "DemoCanaryError",
    "DemoCanaryPolicy",
    "DEFAULT_DEMO_CANARY_POLICY",
    "DemoContractConstraints",
    "DemoLeverageSnapshot",
    "DemoOrderPlan",
    "DemoOrderReport",
    "DemoOrderStatus",
    "DemoTopOfBook",
    "blocked_report",
    "build_demo_order_plan",
    "deterministic_client_order_id",
    "dry_run_report",
    "execute_demo_order_plan",
    "failed_report",
    "load_canonical_demo_order_plan",
    "load_canonical_ready_intent",
)
