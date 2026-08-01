from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from src.exchange.bingx_client import BingXHttpClient
from src.exchange.models import BingXBalance, BingXKline, BingXPosition
from src.risk.kill_switch import KillSwitch
from src.vst_runtime.canary_capture import (
    AsyncCanaryCaptureTransport,
    BingXAsyncCanaryCaptureAdapter,
    CanaryCaptureError,
    CanaryCaptureReport,
    CapturedBalance,
    CapturedIncome,
    capture_canary_inputs,
    create_async_canary_capture_transport,
)
from src.vst_runtime.demo_order import (
    DemoContractConstraints,
    DemoLeverageSnapshot,
    DemoTopOfBook,
    build_demo_order_plan,
    dry_run_report,
    load_canonical_ready_intent,
)
from src.vst_runtime.intent_preparation import (
    IntentPreparationError,
    prepare_demo_canary_intent,
)
from src.vst_runtime.models import RemoteOrder, RemoteOrderStatus, VstConfiguration
from tests.unit.vst_runtime.test_demo_order_cli import DemoFake
from tests.unit.vst_runtime.test_demo_transport import RecordingBingXClient

NOW_MS = 1_767_225_600_000
VST_HOST = "https://open-api-vst.bingx.com"


def _configuration() -> VstConfiguration:
    return VstConfiguration(
        api_key="api-key",
        api_secret="api-secret",
        symbols=frozenset({"BTC-USDT"}),
        maximum_order_notional=Decimal("10"),
        maximum_open_positions=1,
        maximum_session_loss=Decimal("10"),
        maximum_exposure=Decimal("10"),
        configuration_version="capture-test-v1",
    )


class ReadinessFake:
    selected_host = VST_HOST

    def __init__(self, ledger: list[str], *, server_time: int = NOW_MS) -> None:
        self.ledger = ledger
        self.server_time = server_time
        self.closed = False

    async def fetch_server_time(self) -> int:
        self.ledger.append("readiness.server_time")
        return self.server_time

    async def fetch_balance(self) -> tuple[BingXBalance, ...]:
        self.ledger.append("readiness.balance")
        return (BingXBalance("VST", 10, 0, 10, 10, 10),)

    async def fetch_positions(self) -> tuple[()]:
        self.ledger.append("readiness.positions")
        return ()

    async def close(self) -> None:
        self.ledger.append("readiness.close")
        self.closed = True


def _kline(
    minutes_before: int,
    *,
    open_price: str,
    high: str,
    low: str,
    close: str,
) -> BingXKline:
    opened = datetime.fromtimestamp(NOW_MS / 1_000, UTC) - timedelta(
        minutes=minutes_before
    )
    return BingXKline(
        open_time=opened,
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("1"),
        close_time=opened + timedelta(milliseconds=59_999),
        quote_volume=Decimal("100"),
        trades_count=1,
        taker_buy_volume=Decimal("0.5"),
        taker_buy_quote_volume=Decimal("50"),
    )


def _candles() -> tuple[BingXKline, ...]:
    return (
        _kline(3, open_price="98", high="100", low="97", close="99"),
        _kline(2, open_price="99", high="110", low="98", close="100"),
        _kline(1, open_price="100", high="120", low="99", close="100"),
    )


class CaptureFake:
    selected_host = VST_HOST

    def __init__(self, ledger: list[str]) -> None:
        self.ledger = ledger
        self.candles: Sequence[BingXKline] = _candles()
        self.orderbook = DemoTopOfBook(
            "BTC-USDT", Decimal("99"), Decimal("101"), "book-1"
        )
        self.balances: Sequence[CapturedBalance] = (
            CapturedBalance(
                "VST",
                Decimal("10"),
                Decimal("10"),
                Decimal("10"),
                Decimal("0"),
            ),
        )
        self.positions: Sequence[BingXPosition] = ()
        self.constraints = DemoContractConstraints(
            "BTC-USDT",
            Decimal("0.1"),
            Decimal("0.001"),
            Decimal("0.001"),
            Decimal("1"),
            5,
            5,
            True,
        )
        self.leverage = DemoLeverageSnapshot("BTC-USDT", 1, 1)
        self.position_mode = "HEDGE"
        self.open_orders: Sequence[RemoteOrder] = ()
        self.income: Sequence[CapturedIncome] = ()
        self.closed = False
        self.close_error = False

    async def fetch_candles(
        self, symbol: str, timeframe: str, limit: int
    ) -> Sequence[BingXKline]:
        assert (symbol, timeframe, limit) == ("BTC-USDT", "1m", 100)
        self.ledger.append("capture.candles")
        return self.candles

    async def fetch_orderbook(self, symbol: str) -> DemoTopOfBook:
        assert symbol == "BTC-USDT"
        self.ledger.append("capture.orderbook")
        return self.orderbook

    async def fetch_account_balances(self) -> Sequence[CapturedBalance]:
        self.ledger.append("capture.balances")
        return self.balances

    async def fetch_positions(self) -> Sequence[BingXPosition]:
        self.ledger.append("capture.positions")
        return self.positions

    async def fetch_constraints(self, symbol: str) -> DemoContractConstraints:
        assert symbol == "BTC-USDT"
        self.ledger.append("capture.constraints")
        return self.constraints

    async def fetch_leverage(self, symbol: str) -> DemoLeverageSnapshot:
        assert symbol == "BTC-USDT"
        self.ledger.append("capture.leverage")
        return self.leverage

    async def fetch_position_mode(self) -> str:
        self.ledger.append("capture.position_mode")
        return self.position_mode

    async def fetch_open_orders(self, symbol: str) -> Sequence[RemoteOrder]:
        assert symbol == "BTC-USDT"
        self.ledger.append("capture.open_orders")
        return self.open_orders

    async def fetch_income(
        self, *, start_time_ms: int, end_time_ms: int, limit: int
    ) -> Sequence[CapturedIncome]:
        assert start_time_ms <= end_time_ms == NOW_MS
        assert limit == 1_000
        self.ledger.append("capture.income")
        return self.income

    async def close(self) -> None:
        self.ledger.append("capture.close")
        self.closed = True
        if self.close_error:
            raise OSError("fake close failure")


async def _capture(
    tmp_path: Path,
    fake: CaptureFake | None = None,
    *,
    readiness: ReadinessFake | None = None,
    label: str | None = None,
) -> tuple[CanaryCaptureReport, CaptureFake, ReadinessFake, Path, list[str]]:
    ledger: list[str] = [] if fake is None else fake.ledger
    selected_readiness = readiness or ReadinessFake(ledger)
    selected_capture = fake or CaptureFake(ledger)
    parent = tmp_path if label is None else tmp_path / label
    parent.mkdir(exist_ok=True)
    root = parent / ".operator-artifacts"
    report = await capture_canary_inputs(
        _configuration(),
        readiness_provider=lambda _configuration: selected_readiness,
        capture_provider=lambda _configuration, _host: (
            ledger.append("capture.factory") or selected_capture
        ),
        local_kill_switch=KillSwitch(),
        artifact_root=root,
        clock_ms=lambda: NOW_MS,
        monotonic=lambda: 1.0,
    )
    return report, selected_capture, selected_readiness, root, ledger


def _bundle_files(report: CanaryCaptureReport, root: Path) -> dict[str, str]:
    capture_id = report.capture_id
    assert isinstance(capture_id, str)
    directory = root / "canary-inputs" / capture_id
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in directory.iterdir()
        if path.is_file()
    }


@pytest.mark.asyncio
async def test_readiness_precedes_reads_and_bundle_is_canonical_replay_compatible(
    tmp_path: Path,
) -> None:
    report, capture, readiness, root, ledger = await _capture(tmp_path)

    assert report.status == "CAPTURED"
    assert readiness.closed and capture.closed
    assert ledger == [
        "readiness.server_time",
        "readiness.balance",
        "readiness.positions",
        "readiness.close",
        "capture.factory",
        "capture.candles",
        "capture.orderbook",
        "capture.balances",
        "capture.positions",
        "capture.constraints",
        "capture.leverage",
        "capture.position_mode",
        "capture.open_orders",
        "capture.income",
        "capture.close",
    ]
    files = _bundle_files(report, root)
    assert set(files) == {
        "account-input.json",
        "constraints-input.json",
        "manifest.json",
        "market-input.json",
        "policy-input.json",
    }
    for content in files.values():
        assert content == json.dumps(
            json.loads(content), sort_keys=True, separators=(",", ":")
        )
    manifest = json.loads(files["manifest.json"])
    assert manifest["canary_policy"] == {
        "environment": "VST",
        "existing_same_symbol_position_allowed": False,
        "live_supported": False,
        "maximum_leverage": 2,
        "maximum_quote_notional": "10",
        "no_pyramiding": True,
        "order_type": "LIMIT",
        "protected_order_required": True,
        "symbol": "BTC-USDT",
        "ttl_ms": 300_000,
        "version": "bingx-vst-canary-input-policy-v1",
    }
    for filename in (
        "market-input.json",
        "account-input.json",
        "constraints-input.json",
        "policy-input.json",
    ):
        assert manifest["files"][filename] == hashlib.sha256(
            files[filename].encode()
        ).hexdigest()

    intent_root = tmp_path / "prepared" / ".operator-artifacts"
    intent_root.parent.mkdir()
    try:
        prepared = prepare_demo_canary_intent(
            market_json=files["market-input.json"],
            market_digest=manifest["files"]["market-input.json"],
            account_json=files["account-input.json"],
            account_digest=manifest["files"]["account-input.json"],
            constraints_json=files["constraints-input.json"],
            constraints_digest=manifest["files"]["constraints-input.json"],
            policy_json=files["policy-input.json"],
            policy_digest=manifest["files"]["policy-input.json"],
            artifact_directory=intent_root,
            clock_ms=lambda: NOW_MS,
        )
    except IntentPreparationError as error:
        pytest.fail(f"captured inputs were rejected: {error.reason_code}")
    assert prepared.status == "READY"
    assert prepared.intent_digest is not None
    assert prepared.artifact_path is not None

    intent_path = intent_root / Path(prepared.artifact_path).name
    demo = DemoFake()
    intent, verified_digest = load_canonical_ready_intent(
        intent_path.read_text(encoding="utf-8"),
        prepared.intent_digest,
    )
    plan = await build_demo_order_plan(
        intent,
        verified_digest,
        demo,
        clock_ms=lambda: NOW_MS,
    )
    rehearsal = dry_run_report(plan, reported_at_ms=NOW_MS)
    await demo.close()
    assert rehearsal.status.value == "DRY_RUN_READY"
    assert "submit" not in demo.calls and "cancel" not in demo.calls


@pytest.mark.asyncio
async def test_readiness_failure_blocks_transport_creation_and_artifacts(
    tmp_path: Path,
) -> None:
    ledger: list[str] = []
    readiness = ReadinessFake(ledger, server_time=NOW_MS + 20_000)
    provider_calls: list[str] = []
    with pytest.raises(CanaryCaptureError) as caught:
        await capture_canary_inputs(
            _configuration(),
            readiness_provider=lambda _: readiness,
            capture_provider=lambda _configuration, _host: provider_calls.append(
                "capture"
            ),  # type: ignore[arg-type,return-value]
            local_kill_switch=KillSwitch(),
            artifact_root=tmp_path / ".operator-artifacts",
            clock_ms=lambda: NOW_MS,
            monotonic=lambda: 1.0,
        )
    assert caught.value.reason_code == "readiness_clock_drift_exceeded"
    assert provider_calls == []
    assert readiness.closed
    assert not (tmp_path / ".operator-artifacts").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("local_kill_switch", "reason"),
    ((None, "risk_state_unavailable"), ("active", "kill_switch_active")),
)
async def test_local_risk_state_is_required_and_active_state_blocks_before_reads(
    tmp_path: Path,
    local_kill_switch: KillSwitch | str | None,
    reason: str,
) -> None:
    calls: list[str] = []
    switch = KillSwitch()
    if local_kill_switch == "active":
        switch.activate("fake emergency")
        selected: KillSwitch | None = switch
    else:
        selected = None
    with pytest.raises(CanaryCaptureError) as caught:
        await capture_canary_inputs(
            _configuration(),
            readiness_provider=lambda _configuration: calls.append(
                "readiness"
            ),  # type: ignore[arg-type,return-value]
            capture_provider=lambda _configuration, _host: calls.append(
                "capture"
            ),  # type: ignore[arg-type,return-value]
            local_kill_switch=selected,
            artifact_root=tmp_path / ".operator-artifacts",
            clock_ms=lambda: NOW_MS,
            monotonic=lambda: 1.0,
        )
    assert caught.value.reason_code == reason
    assert calls == []
    assert not (tmp_path / ".operator-artifacts").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "reason"),
    (
        ("duplicate", "duplicate_candles"),
        ("stale", "stale_candles"),
        ("gap", "candle_sequence_invalid"),
        ("incomplete", "insufficient_completed_candles"),
    ),
)
async def test_malformed_stale_duplicate_or_incomplete_candles_fail_closed(
    tmp_path: Path,
    case: str,
    reason: str,
) -> None:
    ledger: list[str] = []
    fake = CaptureFake(ledger)
    if case == "duplicate":
        fake.candles = (*_candles(), _candles()[-1])
    elif case == "stale":
        fake.candles = tuple(
            _kline(
                minutes,
                open_price="60",
                high="100",
                low="50",
                close="70",
            )
            for minutes in (8, 7, 6)
        )
    elif case == "gap":
        fake.candles = (
            _kline(4, open_price="60", high="100", low="50", close="70"),
            _candles()[1],
            _candles()[2],
        )
    else:
        fake.candles = _candles()[:2]
    with pytest.raises(CanaryCaptureError) as caught:
        await _capture(tmp_path, fake)
    assert caught.value.reason_code == reason
    assert fake.closed
    assert not (tmp_path / ".operator-artifacts").exists()


def _position() -> BingXPosition:
    return BingXPosition(
        symbol="BTC-USDT",
        position_side="LONG",
        position_amount=Decimal("0.001"),
        entry_price=Decimal("100"),
        mark_price=Decimal("100"),
        unrealized_pnl=Decimal("0"),
        liquidation_price=Decimal("50"),
        leverage=1,
        margin_type="CROSSED",
    )


def _open_order() -> RemoteOrder:
    return RemoteOrder(
        client_order_id="existingcanary",
        order_id="1",
        symbol="BTC-USDT",
        side="BUY",
        order_type="LIMIT",
        status=RemoteOrderStatus.NEW,
        original_quantity=Decimal("0.001"),
        filled_quantity=Decimal("0"),
        average_price=Decimal("0"),
        price=Decimal("99"),
        update_id="1",
        updated_at_ms=NOW_MS,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "reason"),
    (
        ("missing_balance", "incomplete_account_response"),
        ("used_margin", "account_risk_facts_unavailable"),
        ("position", "existing_symbol_position"),
        ("open_order", "existing_open_entry_order"),
        ("income_incomplete", "risk_history_incomplete"),
        ("leverage", "demo_leverage_cap_exceeded"),
        ("mode", "invalid_position_mode_schema"),
        ("constraints", "invalid_constraints_schema"),
    ),
)
async def test_account_risk_and_constraint_facts_fail_instead_of_fabrication(
    tmp_path: Path,
    case: str,
    reason: str,
) -> None:
    ledger: list[str] = []
    fake = CaptureFake(ledger)
    if case == "missing_balance":
        fake.balances = ()
    elif case == "used_margin":
        fake.balances = (
            CapturedBalance("VST", 10, 10, 9, Decimal("1")),
        )
    elif case == "position":
        fake.positions = (_position(),)
    elif case == "open_order":
        fake.open_orders = (_open_order(),)
    elif case == "income_incomplete":
        fake.income = tuple(
            CapturedIncome("REALIZED_PNL", 1, "VST", NOW_MS, str(index))
            for index in range(1_000)
        )
    elif case == "leverage":
        fake.leverage = DemoLeverageSnapshot("BTC-USDT", 3, 1)
    elif case == "mode":
        fake.position_mode = "UNKNOWN"
    else:
        fake.constraints = DemoContractConstraints(
            "ETH-USDT", Decimal("0.1"), Decimal("0.001"), Decimal("0.001"),
            Decimal("1"), 5, 5, True
        )
    with pytest.raises(CanaryCaptureError) as caught:
        await _capture(tmp_path, fake)
    assert caught.value.reason_code == reason
    assert not (tmp_path / ".operator-artifacts").exists()


@pytest.mark.asyncio
async def test_income_risk_is_conservative_deterministic_and_not_fabricated(
    tmp_path: Path,
) -> None:
    ledger: list[str] = []
    fake = CaptureFake(ledger)
    fake.income = (
        CapturedIncome("REALIZED_PNL", "-0.2", "VST", NOW_MS, "loss-2"),
        CapturedIncome("REALIZED_PNL", "-0.1", "VST", NOW_MS, "loss-1"),
        CapturedIncome("TRANSFER", "-5", "VST", NOW_MS, "transfer"),
    )
    report, *_rest, root, _ledger = await _capture(tmp_path, fake)
    account = json.loads(_bundle_files(report, root)["account-input.json"])
    assert account["portfolio"]["daily_loss"] == "0.03"
    assert account["risk_state"]["circuit_breaker_consecutive_losses"] == 2
    assert account["risk_state"]["kill_switch_active"] is False


@pytest.mark.asyncio
async def test_identical_facts_and_time_are_byte_identical_and_changes_are_bound(
    tmp_path: Path,
) -> None:
    first, *_first_rest, first_root, _first_ledger = await _capture(
        tmp_path, label="first"
    )
    second, *_second_rest, second_root, _second_ledger = await _capture(
        tmp_path, label="second"
    )
    first_files = _bundle_files(first, first_root)
    second_files = _bundle_files(second, second_root)
    assert first.capture_id == second.capture_id
    assert first_files == second_files

    ledger: list[str] = []
    changed_fake = CaptureFake(ledger)
    changed_fake.orderbook = DemoTopOfBook(
        "BTC-USDT", Decimal("98"), Decimal("101"), "book-2"
    )
    changed, *_changed_rest, changed_root, _changed_ledger = await _capture(
        tmp_path, changed_fake, label="changed"
    )
    changed_files = _bundle_files(changed, changed_root)
    assert changed.capture_id != first.capture_id
    assert changed_files["market-input.json"] == first_files["market-input.json"]
    assert changed_files["manifest.json"] != first_files["manifest.json"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source", "filename"),
    (
        ("market", "market-input.json"),
        ("account", "account-input.json"),
        ("constraints", "constraints-input.json"),
    ),
)
async def test_meaningful_source_changes_change_the_corresponding_input_digest(
    tmp_path: Path,
    source: str,
    filename: str,
) -> None:
    baseline, *_baseline_rest, baseline_root, _baseline_ledger = await _capture(
        tmp_path, label=f"baseline-{source}"
    )
    ledger: list[str] = []
    changed_fake = CaptureFake(ledger)
    if source == "market":
        values = list(_candles())
        values[-1] = _kline(
            1,
            open_price="100",
            high="121",
            low="99",
            close="101",
        )
        changed_fake.candles = tuple(values)
    elif source == "account":
        changed_fake.balances = (
            CapturedBalance("VST", 11, 11, 11, 0),
        )
    else:
        changed_fake.constraints = DemoContractConstraints(
            "BTC-USDT",
            Decimal("0.01"),
            Decimal("0.001"),
            Decimal("0.001"),
            Decimal("1"),
            5,
            5,
            True,
        )
    changed, *_changed_rest, changed_root, _changed_ledger = await _capture(
        tmp_path,
        changed_fake,
        label=f"changed-{source}",
    )
    baseline_manifest = json.loads(
        _bundle_files(baseline, baseline_root)["manifest.json"]
    )
    changed_manifest = json.loads(
        _bundle_files(changed, changed_root)["manifest.json"]
    )
    assert baseline_manifest["files"][filename] != changed_manifest["files"][
        filename
    ]


@pytest.mark.asyncio
async def test_never_overwrites_and_rejects_symlink_or_wrong_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report, _fake, _readiness, root, _ledger = await _capture(tmp_path)
    original = _bundle_files(report, root)
    with pytest.raises(CanaryCaptureError) as conflict:
        await _capture(tmp_path)
    assert conflict.value.reason_code == "artifact_conflict"
    assert _bundle_files(report, root) == original

    wrong = tmp_path / "wrong"
    with pytest.raises(CanaryCaptureError) as invalid:
        await capture_canary_inputs(
            _configuration(),
            readiness_provider=lambda _: ReadinessFake([]),
            capture_provider=lambda _configuration, _host: CaptureFake([]),
            local_kill_switch=KillSwitch(),
            artifact_root=wrong,
            clock_ms=lambda: NOW_MS,
            monotonic=lambda: 1.0,
        )
    assert invalid.value.reason_code == "artifact_directory_invalid"

    link_parent = tmp_path / "linked"
    link_parent.mkdir()
    link = link_parent / ".operator-artifacts"
    link.mkdir()
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path == link or original_is_symlink(path),
    )
    with pytest.raises(CanaryCaptureError) as symlinked:
        await capture_canary_inputs(
            _configuration(),
            readiness_provider=lambda _: ReadinessFake([]),
            capture_provider=lambda _configuration, _host: CaptureFake([]),
            local_kill_switch=KillSwitch(),
            artifact_root=link,
            clock_ms=lambda: NOW_MS,
            monotonic=lambda: 1.0,
        )
    assert symlinked.value.reason_code == "artifact_directory_invalid"


@pytest.mark.asyncio
async def test_close_failure_blocks_bundle_and_client_closes_on_read_failure(
    tmp_path: Path,
) -> None:
    ledger: list[str] = []
    fake = CaptureFake(ledger)
    fake.close_error = True
    with pytest.raises(CanaryCaptureError) as close_error:
        await _capture(tmp_path, fake)
    assert close_error.value.reason_code == "transport_close_failed"
    assert fake.closed
    assert not (tmp_path / ".operator-artifacts").exists()

    class FailingFake(CaptureFake):
        async def fetch_orderbook(self, symbol: str) -> DemoTopOfBook:
            del symbol
            raise OSError("private transport detail")

    failing = FailingFake([])
    with pytest.raises(CanaryCaptureError) as read_error:
        await _capture(tmp_path, failing, label="read-failure")
    assert read_error.value.reason_code == "capture_read_failed"
    assert failing.closed
    assert "private transport detail" not in str(read_error.value)


def test_adapter_public_surface_contains_only_approved_reads_and_close() -> None:
    public_callables = {
        name
        for name, value in vars(BingXAsyncCanaryCaptureAdapter).items()
        if callable(value) and not name.startswith("_")
    }
    assert public_callables == {
        "close",
        "fetch_account_balances",
        "fetch_candles",
        "fetch_constraints",
        "fetch_income",
        "fetch_leverage",
        "fetch_open_orders",
        "fetch_orderbook",
        "fetch_position_mode",
        "fetch_positions",
    }
    assert {
        "submit",
        "place_order",
        "cancel_order",
        "set_leverage",
        "set_margin_type",
        "set_position_mode",
        "transfer",
        "withdraw",
        "close_position",
    }.isdisjoint(public_callables)


def test_default_factory_wraps_existing_frozen_client_without_network() -> None:
    transport = create_async_canary_capture_transport(_configuration(), VST_HOST)
    assert isinstance(transport, BingXAsyncCanaryCaptureAdapter)
    assert isinstance(transport, AsyncCanaryCaptureTransport)
    assert transport.selected_host == VST_HOST
    hidden_client = transport._BingXAsyncCanaryCaptureAdapter__client
    assert isinstance(hidden_client, BingXHttpClient)


@pytest.mark.asyncio
async def test_concrete_adapter_uses_only_documented_get_mappings() -> None:
    class CaptureRecordingClient(RecordingBingXClient):
        async def get_klines(
            self,
            symbol: str,
            interval: str = "1h",
            limit: int = 500,
            start_time: int | None = None,
            end_time: int | None = None,
        ) -> list[BingXKline]:
            assert start_time is None and end_time is None
            self.calls.append(
                (
                    "GET_KLINES",
                    symbol,
                    {"interval": interval, "limit": limit},
                    False,
                    None,
                )
            )
            return list(_candles())

    client = CaptureRecordingClient()
    client.responses = {
        "/openApi/swap/v3/user/balance": {
            "data": [
                {
                    "asset": "VST",
                    "availableMargin": "10",
                    "balance": "10",
                    "equity": "10",
                    "usedMargin": "0",
                }
            ]
        },
        "/openApi/swap/v2/trade/leverage": {
            "data": {"longLeverage": 1, "shortLeverage": 1}
        },
        "/openApi/swap/v1/positionSide/dual": {
            "data": {"dualSidePosition": True}
        },
        "/openApi/swap/v2/trade/openOrders": {"data": {"orders": []}},
        "/openApi/swap/v2/user/income": {"data": []},
    }
    adapter = BingXAsyncCanaryCaptureAdapter(client)
    assert len(await adapter.fetch_candles("BTC-USDT", "1m", 100)) == 3
    assert (await adapter.fetch_orderbook("BTC-USDT")).symbol == "BTC-USDT"
    assert len(await adapter.fetch_account_balances()) == 1
    assert len(await adapter.fetch_positions()) == 1
    assert (await adapter.fetch_constraints("BTC-USDT")).symbol == "BTC-USDT"
    assert (await adapter.fetch_leverage("BTC-USDT")).long_leverage == 1
    assert await adapter.fetch_position_mode() == "HEDGE"
    assert tuple(await adapter.fetch_open_orders("BTC-USDT")) == ()
    assert tuple(
        await adapter.fetch_income(
            start_time_ms=NOW_MS - 1_000,
            end_time_ms=NOW_MS,
            limit=1_000,
        )
    ) == ()
    await adapter.close()
    assert client.closed_by_adapter
    assert {
        (call[0], call[1]) for call in client.calls if call[0] == "GET"
    } == {
        ("GET", "/openApi/swap/v3/user/balance"),
        ("GET", "/openApi/swap/v2/trade/leverage"),
        ("GET", "/openApi/swap/v1/positionSide/dual"),
        ("GET", "/openApi/swap/v2/trade/openOrders"),
        ("GET", "/openApi/swap/v2/user/income"),
    }


@pytest.mark.asyncio
async def test_fake_capture_never_reaches_http_or_any_exchange_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def forbidden(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("exchange operation reached")

    for method in (
        "request",
        "place_order",
        "cancel_order",
        "set_leverage",
        "set_margin_type",
        "set_position_mode",
        "close_all_positions",
    ):
        monkeypatch.setattr(BingXHttpClient, method, forbidden)
    report, capture, readiness, _root, _ledger = await _capture(tmp_path)
    assert report.status == "CAPTURED"
    assert capture.closed and readiness.closed
