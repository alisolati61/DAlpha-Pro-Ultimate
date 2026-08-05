from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from src.exchange.models import BingXBalance, BingXPosition, BingXPositionSide
from src.execution_intent.models import (
    ExecutionIntent,
    IntentOrderType,
    IntentReason,
    IntentSide,
    IntentStatus,
    IntentTimeInForce,
    OrderSpecification,
)
from src.vst_runtime.demo_order import (
    DemoAmbiguousSubmission,
    DemoCanaryError,
    DemoContractConstraints,
    DemoLeverageSnapshot,
    DemoOrderPlan,
    DemoOrderStatus,
    DemoTopOfBook,
    build_demo_order_plan,
    deterministic_client_order_id,
    dry_run_report,
    execute_demo_order_plan,
    load_canonical_demo_order_plan,
    load_canonical_ready_intent,
)
from src.vst_runtime.models import RemoteOrder, RemoteOrderStatus

NOW_MS = 1_800_000_000_000
VST_HOST = "https://open-api-vst.bingx.com"


def order_spec(
    side: IntentSide,
    order_type: IntentOrderType,
    price: str,
    quantity: str = "0.05",
    *,
    reduce_only: bool,
) -> OrderSpecification:
    return OrderSpecification(
        side=side,
        order_type=order_type,
        price=Decimal(price),
        quantity=Decimal(quantity),
        time_in_force=IntentTimeInForce.GTC,
        reduce_only=reduce_only,
    )


def ready_intent(
    *,
    side: IntentSide = IntentSide.BUY,
    price: str | None = None,
    quantity: str = "0.05",
    stop: str | None = None,
    take: str | None = None,
    source_ms: int = NOW_MS - 1_000,
    exchange: str = "BingX",
) -> ExecutionIntent:
    if side is IntentSide.BUY:
        entry_price, stop_price, take_price = (
            price or "100",
            stop or "90",
            take or "110",
        )
        protection_side = IntentSide.SELL
    else:
        entry_price, stop_price, take_price = (
            price or "102",
            stop or "110",
            take or "90",
        )
        protection_side = IntentSide.BUY
    return ExecutionIntent(
        intent_id="intent-demo-001",
        decision_id="decision-demo-001",
        status=IntentStatus.READY,
        symbol="BTC-USDT",
        exchange=exchange,
        timeframe="1h",
        entry=order_spec(
            side,
            IntentOrderType.LIMIT,
            entry_price,
            quantity,
            reduce_only=False,
        ),
        stop_loss=order_spec(
            protection_side,
            IntentOrderType.STOP,
            stop_price,
            quantity,
            reduce_only=True,
        ),
        take_profit=order_spec(
            protection_side,
            IntentOrderType.TAKE_PROFIT,
            take_price,
            quantity,
            reduce_only=True,
        ),
        strategy_id="strategy-demo",
        strategy_version="1",
        risk_amount=Decimal("1"),
        constraints_id="approved-constraints",
        source_timestamp=datetime.fromtimestamp(source_ms / 1_000, UTC),
        reason_codes=(IntentReason.INTENT_READY,),
    )


def intent_digest(intent: ExecutionIntent) -> str:
    return hashlib.sha256(intent.to_json().encode()).hexdigest()


def balance(*, available: str = "100") -> BingXBalance:
    return BingXBalance(
        "VST",
        Decimal("100"),
        Decimal(0),
        Decimal("100"),
        Decimal(available),
        Decimal(available),
    )


def position(*, amount: str = "0") -> BingXPosition:
    return BingXPosition(
        "BTC-USDT",
        BingXPositionSide.LONG,
        Decimal(amount),
        Decimal("100"),
        Decimal("100"),
        Decimal(0),
        Decimal(0),
        1,
        "CROSSED",
    )


def constraints(**changes: Any) -> DemoContractConstraints:
    values: dict[str, Any] = {
        "symbol": "BTC-USDT",
        "price_tick": Decimal("0.1"),
        "quantity_step": Decimal("0.001"),
        "minimum_quantity": Decimal("0.001"),
        "minimum_notional": Decimal("1"),
        "maximum_long_leverage": 5,
        "maximum_short_leverage": 5,
        "trading_enabled": True,
    }
    values.update(changes)
    return DemoContractConstraints(**values)


def standalone_order(
    *,
    client_order_id: str = "anotherorder",
    status: RemoteOrderStatus = RemoteOrderStatus.NEW,
    filled: str = "0",
    symbol: str = "BTC-USDT",
    side: str = "BUY",
    quantity: str = "0.05",
    price: str = "100",
) -> RemoteOrder:
    return RemoteOrder(
        client_order_id=client_order_id,
        order_id="remote-1",
        symbol=symbol,
        side=side,
        order_type="LIMIT",
        status=status,
        original_quantity=Decimal(quantity),
        filled_quantity=Decimal(filled),
        average_price=Decimal("0"),
        price=Decimal(price),
        update_id="update-1",
        updated_at_ms=NOW_MS,
    )


def plan_order(
    plan: DemoOrderPlan,
    status: RemoteOrderStatus,
    *,
    filled: str = "0",
    client_order_id: str | None = None,
) -> RemoteOrder:
    return standalone_order(
        client_order_id=client_order_id or plan.client_order_id,
        status=status,
        filled=filled,
        symbol=plan.symbol,
        side=plan.side,
        quantity=str(plan.quantity),
        price=str(plan.limit_price),
    )


class FakeDemoTransport:
    def __init__(self) -> None:
        self.selected_host = VST_HOST
        self.constraints: object = constraints()
        self.book: object = DemoTopOfBook(
            "BTC-USDT", Decimal("99"), Decimal("101"), "book-1"
        )
        self.balances: object = (balance(),)
        self.positions: object = ()
        self.leverage: object = DemoLeverageSnapshot("BTC-USDT", 1, 1)
        self.position_mode: object = "HEDGE"
        self.preflight_order: object = None
        self.open_orders: object = ()
        self.open_order_results: list[object] = []
        self.recent_orders: object = ()
        self.submit_result: RemoteOrder | None = None
        self.submit_error: Exception | None = None
        self.query_results: list[RemoteOrder | None | Exception] = []
        self.cancel_result: RemoteOrder | None = None
        self.cancel_error: Exception | None = None
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.closed = False

    async def fetch_constraints(self, symbol: str) -> DemoContractConstraints:
        self.calls.append(("fetch_constraints", (symbol,)))
        return self.constraints  # type: ignore[return-value]

    async def fetch_orderbook(self, symbol: str) -> DemoTopOfBook:
        self.calls.append(("fetch_orderbook", (symbol,)))
        return self.book  # type: ignore[return-value]

    async def fetch_balances(self) -> Sequence[BingXBalance]:
        self.calls.append(("fetch_balances", ()))
        return self.balances  # type: ignore[return-value]

    async def fetch_positions(self, symbol: str) -> Sequence[BingXPosition]:
        self.calls.append(("fetch_positions", (symbol,)))
        return self.positions  # type: ignore[return-value]

    async def fetch_leverage(self, symbol: str) -> DemoLeverageSnapshot:
        self.calls.append(("fetch_leverage", (symbol,)))
        return self.leverage  # type: ignore[return-value]

    async def fetch_position_mode(self) -> str:
        self.calls.append(("fetch_position_mode", ()))
        return self.position_mode  # type: ignore[return-value]

    async def fetch_open_orders(self, symbol: str) -> Sequence[RemoteOrder]:
        self.calls.append(("fetch_open_orders", (symbol,)))
        if self.open_order_results:
            return self.open_order_results.pop(0)  # type: ignore[return-value]
        return self.open_orders  # type: ignore[return-value]

    async def fetch_recent_orders(self, symbol: str) -> Sequence[RemoteOrder]:
        self.calls.append(("fetch_recent_orders", (symbol,)))
        return self.recent_orders  # type: ignore[return-value]

    async def submit_protected_limit(self, plan: DemoOrderPlan) -> RemoteOrder:
        self.calls.append(("submit_protected_limit", (plan.client_order_id,)))
        if self.submit_error is not None:
            raise self.submit_error
        return self.submit_result or plan_order(plan, RemoteOrderStatus.NEW)

    async def query_order(
        self, symbol: str, client_order_id: str
    ) -> RemoteOrder | None:
        self.calls.append(("query_order", (symbol, client_order_id)))
        if self.query_results:
            result = self.query_results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result
        return self.preflight_order  # type: ignore[return-value]

    async def cancel_order(
        self, symbol: str, client_order_id: str
    ) -> RemoteOrder | None:
        self.calls.append(("cancel_order", (symbol, client_order_id)))
        if self.cancel_error is not None:
            raise self.cancel_error
        return self.cancel_result

    async def close(self) -> None:
        self.calls.append(("close", ()))
        self.closed = True


async def build_plan(
    fake: FakeDemoTransport,
    intent: ExecutionIntent | None = None,
) -> DemoOrderPlan:
    chosen = intent or ready_intent()
    return await build_demo_order_plan(
        chosen,
        intent_digest(chosen),
        fake,
        clock_ms=lambda: NOW_MS,
    )


def test_canonical_ready_intent_requires_exact_digest_status_and_shape() -> None:
    intent = ready_intent()
    serialized = intent.to_json()
    digest = intent_digest(intent)
    loaded, verified = load_canonical_ready_intent(serialized, digest)
    assert loaded == intent
    assert verified == digest

    with pytest.raises(DemoCanaryError, match="intent_digest_mismatch"):
        load_canonical_ready_intent(serialized, "0" * 64)

    pretty = json.dumps(json.loads(serialized), indent=2, sort_keys=True)
    with pytest.raises(DemoCanaryError, match="intent_not_canonical"):
        load_canonical_ready_intent(
            pretty, hashlib.sha256(pretty.encode()).hexdigest()
        )

    for status in (IntentStatus.BLOCKED.value, IntentStatus.NO_ACTION.value):
        payload = json.loads(serialized)
        payload["status"] = status
        changed = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with pytest.raises(DemoCanaryError, match="intent_not_ready"):
            load_canonical_ready_intent(
                changed, hashlib.sha256(changed.encode()).hexdigest()
            )

    payload = json.loads(serialized)
    payload["unexpected"] = True
    changed = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    with pytest.raises(DemoCanaryError, match="invalid_intent_contract"):
        load_canonical_ready_intent(
            changed, hashlib.sha256(changed.encode()).hexdigest()
        )


def _tampered_plan_json(plan: DemoOrderPlan, **changes: object) -> str:
    payload = json.loads(plan.to_json())
    payload.update(changes)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


@pytest.mark.asyncio
async def test_canonical_plan_loader_round_trips_exact_bytes() -> None:
    fake = FakeDemoTransport()
    plan = await build_plan(fake)
    loaded = load_canonical_demo_order_plan(plan.to_json())
    assert loaded == plan
    assert loaded.digest == plan.digest


@pytest.mark.asyncio
async def test_canonical_plan_loader_rejects_tampered_field() -> None:
    fake = FakeDemoTransport()
    plan = await build_plan(fake)
    tampered = _tampered_plan_json(
        plan,
        quantity="0.06",
        notional=str(Decimal("0.06") * plan.limit_price),
    )
    with pytest.raises(DemoCanaryError, match="plan_artifact_digest_mismatch"):
        load_canonical_demo_order_plan(tampered)


@pytest.mark.asyncio
async def test_canonical_plan_loader_rejects_tampered_embedded_digest() -> None:
    fake = FakeDemoTransport()
    plan = await build_plan(fake)
    tampered = _tampered_plan_json(plan, digest="0" * 64)
    with pytest.raises(DemoCanaryError, match="plan_artifact_digest_mismatch"):
        load_canonical_demo_order_plan(tampered)


@pytest.mark.asyncio
async def test_canonical_plan_loader_rejects_blank_embedded_digest() -> None:
    fake = FakeDemoTransport()
    plan = await build_plan(fake)
    tampered = _tampered_plan_json(plan, digest="")
    with pytest.raises(DemoCanaryError, match="invalid_plan_schema"):
        load_canonical_demo_order_plan(tampered)


@pytest.mark.asyncio
async def test_canonical_plan_loader_rejects_missing_field() -> None:
    fake = FakeDemoTransport()
    plan = await build_plan(fake)
    payload = json.loads(plan.to_json())
    del payload["notional"]
    changed = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    with pytest.raises(DemoCanaryError, match="invalid_plan_schema"):
        load_canonical_demo_order_plan(changed)


@pytest.mark.asyncio
async def test_canonical_plan_loader_rejects_unexpected_field() -> None:
    fake = FakeDemoTransport()
    plan = await build_plan(fake)
    tampered = _tampered_plan_json(plan, unexpected=True)
    with pytest.raises(DemoCanaryError, match="invalid_plan_schema"):
        load_canonical_demo_order_plan(tampered)


@pytest.mark.asyncio
async def test_canonical_plan_loader_rejects_malformed_decimal() -> None:
    fake = FakeDemoTransport()
    plan = await build_plan(fake)
    tampered = _tampered_plan_json(plan, quantity="not-a-number")
    with pytest.raises(DemoCanaryError, match="invalid_plan_schema"):
        load_canonical_demo_order_plan(tampered)


@pytest.mark.asyncio
async def test_canonical_plan_loader_rejects_boolean_numeric_field() -> None:
    fake = FakeDemoTransport()
    plan = await build_plan(fake)
    tampered = _tampered_plan_json(plan, leverage=True)
    with pytest.raises(DemoCanaryError, match="invalid_plan_schema"):
        load_canonical_demo_order_plan(tampered)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_value", ["NaN", "Infinity", "-Infinity"])
async def test_canonical_plan_loader_rejects_non_finite_decimal(
    bad_value: str,
) -> None:
    fake = FakeDemoTransport()
    plan = await build_plan(fake)
    tampered = _tampered_plan_json(plan, quantity=bad_value)
    with pytest.raises(DemoCanaryError, match="invalid_plan_schema"):
        load_canonical_demo_order_plan(tampered)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("side", "expected_position_side"),
    [(IntentSide.BUY, "LONG"), (IntentSide.SELL, "SHORT")],
)
async def test_dry_plan_is_nonmarket_read_only_and_deterministic(
    side: IntentSide, expected_position_side: str
) -> None:
    fake = FakeDemoTransport()
    intent = ready_intent(side=side)
    plan = await build_plan(fake, intent)
    report = dry_run_report(plan, reported_at_ms=NOW_MS)

    assert plan.side == side.value
    assert plan.position_side == expected_position_side
    assert plan.notional == plan.quantity * plan.limit_price
    assert plan.client_order_id == deterministic_client_order_id(intent.intent_id)
    assert plan.selected_host == VST_HOST
    assert plan.digest == DemoOrderPlan(**plan.to_dict()).digest
    assert report.status is DemoOrderStatus.DRY_RUN_READY
    assert report.digest == dry_run_report(plan, reported_at_ms=NOW_MS).digest
    assert [name for name, _ in fake.calls] == [
        "fetch_constraints",
        "fetch_orderbook",
        "fetch_balances",
        "fetch_positions",
        "fetch_leverage",
        "fetch_position_mode",
        "query_order",
        "fetch_open_orders",
        "fetch_recent_orders",
    ]
    assert not any(
        name in {"submit_protected_limit", "cancel_order"}
        for name, _ in fake.calls
    )

    oversized = plan.to_dict()
    oversized_quantity = Decimal("0.2")
    oversized.update(
        {
            "digest": "",
            "notional": oversized_quantity * plan.limit_price,
            "quantity": oversized_quantity,
        }
    )
    with pytest.raises(ValueError, match="bounds"):
        DemoOrderPlan(**oversized)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_one_way_account_uses_required_both_position_side() -> None:
    fake = FakeDemoTransport()
    fake.position_mode = "ONE_WAY"
    plan = await build_plan(fake)
    assert plan.position_side == "BOTH"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("buy_marketable", "marketable_limit_price"),
        ("sell_marketable", "marketable_limit_price"),
        ("quantity_step", "quantity_not_exchange_normalized"),
        ("price_tick", "price_not_exchange_normalized"),
        ("minimum_quantity", "quantity_below_exchange_minimum"),
        ("minimum_notional", "notional_below_exchange_minimum"),
        ("notional_cap", "demo_notional_cap_exceeded"),
        ("leverage", "demo_leverage_cap_exceeded"),
        ("leverage_symbol", "invalid_leverage_schema"),
        ("position_mode", "invalid_position_mode_schema"),
        ("margin", "insufficient_available_margin"),
        ("position", "existing_symbol_position"),
        ("preflight_duplicate", "duplicate_client_order_id"),
        ("open_duplicate", "duplicate_client_order_id"),
        ("other_open_entry", "existing_open_entry_order"),
        ("protection", "invalid_protection_prices"),
        ("disabled", "unsupported_symbol"),
    ],
)
async def test_plan_fail_closed_constraints_and_account_guards(
    case: str, reason: str
) -> None:
    fake = FakeDemoTransport()
    intent = ready_intent()
    if case == "buy_marketable":
        intent = ready_intent(price="101")
    elif case == "sell_marketable":
        intent = ready_intent(side=IntentSide.SELL, price="99")
    elif case == "quantity_step":
        intent = ready_intent(quantity="0.0505")
    elif case == "price_tick":
        intent = ready_intent(price="100.05")
    elif case == "minimum_quantity":
        fake.constraints = constraints(minimum_quantity=Decimal("0.1"))
    elif case == "minimum_notional":
        fake.constraints = constraints(minimum_notional=Decimal("6"))
    elif case == "notional_cap":
        intent = ready_intent(quantity="0.11")
    elif case == "leverage":
        fake.leverage = DemoLeverageSnapshot("BTC-USDT", 3, 1)
    elif case == "leverage_symbol":
        fake.leverage = DemoLeverageSnapshot("ETH-USDT", 1, 1)
    elif case == "position_mode":
        fake.position_mode = "UNKNOWN"
    elif case == "margin":
        fake.balances = (balance(available="0.1"),)
    elif case == "position":
        fake.positions = (position(amount="0.01"),)
    elif case == "preflight_duplicate":
        fake.preflight_order = standalone_order(
            client_order_id=deterministic_client_order_id(intent.intent_id)
        )
    elif case == "open_duplicate":
        fake.open_orders = (
            standalone_order(
                client_order_id=deterministic_client_order_id(intent.intent_id)
            ),
        )
    elif case == "other_open_entry":
        fake.open_orders = (
            standalone_order(client_order_id="anotherentryorder"),
        )
    elif case == "protection":
        intent = ready_intent(stop="100")
    elif case == "disabled":
        fake.constraints = constraints(trading_enabled=False)

    with pytest.raises(DemoCanaryError, match=reason):
        await build_plan(fake, intent)
    assert not any(
        name in {"submit_protected_limit", "cancel_order"}
        for name, _ in fake.calls
    )


@pytest.mark.asyncio
async def test_intent_expiry_and_future_timestamp_fail_before_remote_reads() -> None:
    for intent, reason in (
        (ready_intent(source_ms=NOW_MS - 300_001), "intent_expired"),
        (ready_intent(source_ms=NOW_MS + 5_001), "intent_timestamp_invalid"),
    ):
        fake = FakeDemoTransport()
        with pytest.raises(DemoCanaryError, match=reason):
            await build_plan(fake, intent)
        assert fake.calls == []


@pytest.mark.asyncio
async def test_submit_query_cancel_query_reconcile_exactly_once() -> None:
    fake = FakeDemoTransport()
    plan = await build_plan(fake)
    fake.calls.clear()
    fake.query_results = [
        None,
        plan_order(plan, RemoteOrderStatus.NEW),
        plan_order(plan, RemoteOrderStatus.CANCELED),
    ]

    report = await execute_demo_order_plan(
        plan,
        fake,
        approved_plan_digest=plan.digest,
        typed_confirmation=f"SUBMIT {plan.client_order_id}",
        clock_ms=lambda: NOW_MS,
    )

    assert report.status is DemoOrderStatus.RECONCILED
    assert report.transitions == (
        DemoOrderStatus.SUBMITTED,
        DemoOrderStatus.CANCELLED,
        DemoOrderStatus.RECONCILED,
    )
    assert [name for name, _ in fake.calls] == [
        "fetch_constraints",
        "fetch_positions",
        "fetch_leverage",
        "fetch_position_mode",
        "fetch_open_orders",
        "fetch_orderbook",
        "query_order",
        "submit_protected_limit",
        "query_order",
        "cancel_order",
        "query_order",
        "fetch_positions",
        "fetch_open_orders",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "submit_error",
    [DemoAmbiguousSubmission(), RuntimeError("raw-secret")],
)
async def test_ambiguous_submit_is_never_resubmitted(
    submit_error: Exception,
) -> None:
    fake = FakeDemoTransport()
    plan = await build_plan(fake)
    fake.calls.clear()
    fake.submit_error = submit_error
    fake.query_results = [None, None]

    report = await execute_demo_order_plan(
        plan,
        fake,
        approved_plan_digest=plan.digest,
        typed_confirmation=f"SUBMIT {plan.client_order_id}",
        clock_ms=lambda: NOW_MS,
    )

    assert report.status is DemoOrderStatus.AMBIGUOUS
    assert report.kill_switch.active
    assert "do_not_resubmit" in report.recommended_actions
    assert [name for name, _ in fake.calls].count("submit_protected_limit") == 1
    assert not any(name == "cancel_order" for name, _ in fake.calls)
    assert "raw-secret" not in report.to_json()


@pytest.mark.asyncio
async def test_unexpected_fill_is_fail_closed_without_resubmit_or_flatten() -> None:
    fake = FakeDemoTransport()
    plan = await build_plan(fake)
    fake.calls.clear()
    fake.query_results = [
        None,
        plan_order(plan, RemoteOrderStatus.FILLED, filled="0.05"),
    ]

    report = await execute_demo_order_plan(
        plan,
        fake,
        approved_plan_digest=plan.digest,
        typed_confirmation=f"SUBMIT {plan.client_order_id}",
        clock_ms=lambda: NOW_MS,
    )

    assert report.status is DemoOrderStatus.UNEXPECTED_FILL
    assert report.kill_switch.active
    assert [name for name, _ in fake.calls].count("submit_protected_limit") == 1
    assert not any(name == "cancel_order" for name, _ in fake.calls)


@pytest.mark.asyncio
async def test_open_orders_endpoint_presence_prevents_false_reconciliation() -> None:
    fake = FakeDemoTransport()
    plan = await build_plan(fake)
    fake.calls.clear()
    fake.query_results = [
        None,
        plan_order(plan, RemoteOrderStatus.CANCELED),
    ]
    fake.open_orders = (
        plan_order(plan, RemoteOrderStatus.CANCELED),
    )
    fake.open_order_results = [(), fake.open_orders]

    report = await execute_demo_order_plan(
        plan,
        fake,
        approved_plan_digest=plan.digest,
        typed_confirmation=f"SUBMIT {plan.client_order_id}",
        clock_ms=lambda: NOW_MS,
    )

    assert report.status is DemoOrderStatus.AMBIGUOUS
    assert report.kill_switch.active
    assert "canary_order_still_open" in report.reason_codes


@pytest.mark.asyncio
@pytest.mark.parametrize("gate", ["digest", "confirmation", "expiry"])
async def test_approval_gates_precede_every_write(gate: str) -> None:
    fake = FakeDemoTransport()
    plan = await build_plan(fake)
    fake.calls.clear()
    approved = plan.digest
    typed = f"SUBMIT {plan.client_order_id}"
    now = NOW_MS
    expected = ""
    if gate == "digest":
        approved = "0" * 64
        expected = "plan_digest_mismatch"
    elif gate == "confirmation":
        typed = f"submit {plan.client_order_id}"
        expected = "typed_confirmation_mismatch"
    else:
        now = plan.expires_at_ms + 1
        expected = "plan_expired"

    with pytest.raises(DemoCanaryError, match=expected):
        await execute_demo_order_plan(
            plan,
            fake,
            approved_plan_digest=approved,
            typed_confirmation=typed,
            clock_ms=lambda: now,
        )
    assert fake.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [False, True])
async def test_final_duplicate_check_precedes_the_only_submission(
    failure: bool,
) -> None:
    fake = FakeDemoTransport()
    plan = await build_plan(fake)
    fake.calls.clear()
    fake.query_results = [
        (
            DemoCanaryError("order_query_failed")
            if failure
            else plan_order(plan, RemoteOrderStatus.CANCELED)
        )
    ]
    reason = (
        "order_query_failed" if failure else "duplicate_client_order_id"
    )

    with pytest.raises(DemoCanaryError, match=reason):
        await execute_demo_order_plan(
            plan,
            fake,
            approved_plan_digest=plan.digest,
            typed_confirmation=f"SUBMIT {plan.client_order_id}",
            clock_ms=lambda: NOW_MS,
        )
    assert [name for name, _ in fake.calls] == [
        "fetch_constraints",
        "fetch_positions",
        "fetch_leverage",
        "fetch_position_mode",
        "fetch_open_orders",
        "fetch_orderbook",
        "query_order",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("constraints", "constraints_snapshot_changed"),
        ("market", "marketable_limit_price"),
        ("position", "existing_symbol_position"),
        ("leverage", "pre_submit_leverage_changed"),
        ("position_mode", "pre_submit_position_mode_changed"),
        ("open_order", "existing_open_entry_order"),
    ],
)
async def test_latest_pre_submit_state_is_revalidated_after_confirmation(
    case: str,
    reason: str,
) -> None:
    fake = FakeDemoTransport()
    plan = await build_plan(fake)
    fake.calls.clear()
    fake.query_results = [None]
    if case == "constraints":
        fake.constraints = constraints(minimum_notional=Decimal("2"))
    elif case == "market":
        fake.book = DemoTopOfBook(
            plan.symbol,
            Decimal("99"),
            plan.limit_price,
            "moved",
        )
    elif case == "position":
        fake.positions = (position(amount="0.01"),)
    elif case == "leverage":
        fake.leverage = DemoLeverageSnapshot(plan.symbol, 3, 1)
    elif case == "position_mode":
        fake.position_mode = "ONE_WAY"
    else:
        fake.open_orders = (
            standalone_order(client_order_id="anotherentryorder"),
        )

    with pytest.raises(DemoCanaryError, match=reason):
        await execute_demo_order_plan(
            plan,
            fake,
            approved_plan_digest=plan.digest,
            typed_confirmation=f"SUBMIT {plan.client_order_id}",
            clock_ms=lambda: NOW_MS,
        )
    assert not any(
        name in {"submit_protected_limit", "cancel_order"}
        for name, _ in fake.calls
    )


@pytest.mark.asyncio
async def test_final_order_identity_is_revalidated_after_cancel() -> None:
    fake = FakeDemoTransport()
    plan = await build_plan(fake)
    fake.calls.clear()
    fake.query_results = [
        None,
        plan_order(plan, RemoteOrderStatus.NEW),
        plan_order(
            plan,
            RemoteOrderStatus.CANCELED,
            client_order_id="differentclient",
        ),
    ]

    report = await execute_demo_order_plan(
        plan,
        fake,
        approved_plan_digest=plan.digest,
        typed_confirmation=f"SUBMIT {plan.client_order_id}",
        clock_ms=lambda: NOW_MS,
    )
    assert report.status is DemoOrderStatus.FAILED
    assert "remote_order_identity_mismatch" in report.reason_codes
    assert report.kill_switch.active
