from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import pytest

import scripts.bingx_vst_watch_canary as command
from src.execution_intent.models import IntentStatus
from src.risk.kill_switch import KillSwitch
from src.vst_runtime.canary_capture import (
    CanaryCaptureError,
    CanaryCaptureReport,
)
from src.vst_runtime.demo_order import (
    DemoCanaryError,
    DemoOrderStatus,
    build_demo_order_plan,
    dry_run_report,
)
from src.vst_runtime.intent_preparation import IntentPreparationReport
from src.vst_runtime.models import VstConfiguration
from tests.unit.vst_runtime.test_demo_order import (
    NOW_MS,
    VST_HOST,
    FakeDemoTransport,
    intent_digest,
    ready_intent,
)
from tests.unit.vst_runtime.test_demo_order_cli import ReadinessFake


@dataclass
class FakeTime:
    wall_ms: int = NOW_MS + 10_000
    monotonic_seconds: float = 10.0
    delays: list[float] = field(default_factory=list)

    def clock_ms(self) -> int:
        return self.wall_ms

    def monotonic(self) -> float:
        return self.monotonic_seconds

    async def sleep(self, delay: float) -> None:
        self.delays.append(delay)
        self.wall_ms += round(delay * 1_000)
        self.monotonic_seconds += delay


def _configuration() -> VstConfiguration:
    return VstConfiguration(
        api_key="vst-key",
        api_secret="vst-secret",
        symbols=frozenset({"BTC-USDT"}),
        maximum_order_notional=Decimal("10"),
        maximum_open_positions=1,
        maximum_session_loss=Decimal("10"),
        maximum_exposure=Decimal("10"),
        configuration_version="canary-watch-test-v1",
        base_url=VST_HOST,
        maximum_clock_drift_ms=2_000,
    )


def _capture(index: int = 1) -> CanaryCaptureReport:
    capture_id = f"{index:064x}"
    return CanaryCaptureReport(
        status="CAPTURED",
        capture_id=capture_id,
        artifact_directory=f".operator-artifacts/canary-inputs/{capture_id}",
        selected_host=VST_HOST,
        created_at="2027-01-15T08:00:00Z",
        expires_at="2027-01-15T08:05:00Z",
        input_digests=(),
        preparation_command="python prepare",
        dry_run_command="python dry-run",
        reason_codes=("capture_complete",),
    )


def _hold() -> IntentPreparationReport:
    return IntentPreparationReport(
        artifact_path=None,
        intent_digest=None,
        status=IntentStatus.NO_ACTION.value,
        symbol="BTC-USDT",
        side=None,
        expires_at=None,
        proposal_id="proposal-hold",
        decision_id="decision-hold",
        risk_evaluation_id=None,
        reason_codes=("decision_hold",),
    )


def _ready() -> IntentPreparationReport:
    artifact_id = "a" * 64
    return IntentPreparationReport(
        artifact_path=f".operator-artifacts/{artifact_id}.json",
        intent_digest="b" * 64,
        status=IntentStatus.READY.value,
        symbol="BTC-USDT",
        side="BUY",
        expires_at="2027-01-15T08:05:00Z",
        proposal_id="proposal-ready",
        decision_id="decision-ready",
        risk_evaluation_id="risk-ready",
        reason_codes=("intent_ready",),
    )


def _write_ready_artifact(artifact_root: Path) -> IntentPreparationReport:
    artifact_root.mkdir()
    artifact_id = "a" * 64
    intent = ready_intent(source_ms=NOW_MS - 1_000)
    serialized = intent.to_json()
    digest = hashlib.sha256(serialized.encode()).hexdigest()
    (artifact_root / f"{artifact_id}.json").write_text(
        serialized,
        encoding="utf-8",
    )
    return IntentPreparationReport(
        artifact_path=f".operator-artifacts/{artifact_id}.json",
        intent_digest=digest,
        status=IntentStatus.READY.value,
        symbol="BTC-USDT",
        side="BUY",
        expires_at="2027-01-15T08:05:00Z",
        proposal_id="proposal-ready",
        decision_id="decision-ready",
        risk_evaluation_id="risk-ready",
        reason_codes=("intent_ready",),
    )


async def _dry_run_result():
    intent = ready_intent(source_ms=NOW_MS - 1_000)
    transport = FakeDemoTransport()
    try:
        plan = await build_demo_order_plan(
            intent,
            intent_digest(intent),
            transport,
            clock_ms=lambda: NOW_MS,
        )
        return dry_run_report(plan, reported_at_ms=NOW_MS)
    finally:
        await transport.close()


def _unused_provider(*args: object, **kwargs: object) -> object:
    del args, kwargs
    raise AssertionError("provider must not be composed by the stubbed boundary")


def test_default_demo_factory_passes_selected_host_by_keyword(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = FakeDemoTransport()
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def factory(*args: object, **kwargs: object) -> FakeDemoTransport:
        calls.append((args, kwargs))
        return expected

    monkeypatch.setattr(command, "create_async_demo_order_transport", factory)
    configuration = _configuration()

    assert command._default_demo_transport_provider(
        configuration,
        VST_HOST,
    ) is expected
    assert calls == [((configuration,), {"selected_host": VST_HOST})]


@pytest.mark.asyncio
async def test_scheduler_uses_latest_settled_boundary_without_burst_catchup() -> None:
    fake_time = FakeTime()
    deadline = fake_time.monotonic() + 200

    first = await command._wait_for_closed_candle(
        clock_ms=fake_time.clock_ms,
        monotonic=fake_time.monotonic,
        sleeper=fake_time.sleep,
        deadline=deadline,
        after_boundary_ms=None,
    )
    assert first == NOW_MS
    assert fake_time.delays == []

    fake_time.wall_ms += 75_000
    fake_time.monotonic_seconds += 75
    second = await command._wait_for_closed_candle(
        clock_ms=fake_time.clock_ms,
        monotonic=fake_time.monotonic,
        sleeper=fake_time.sleep,
        deadline=deadline,
        after_boundary_ms=first,
    )
    assert second == NOW_MS + 60_000
    assert fake_time.delays == []


@pytest.mark.asyncio
async def test_hold_watch_is_bounded_and_samples_only_closed_minute_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_time = FakeTime()
    sampled_at: list[int] = []
    prepared = 0

    async def capture(*args: object, **kwargs: object) -> CanaryCaptureReport:
        del args, kwargs
        sampled_at.append(fake_time.clock_ms())
        return _capture(len(sampled_at))

    def prepare(*args: object, **kwargs: object) -> IntentPreparationReport:
        nonlocal prepared
        del args, kwargs
        prepared += 1
        return _hold()

    monkeypatch.setattr(command, "capture_canary_inputs", capture)
    monkeypatch.setattr(command, "_prepare_capture", prepare)
    progress: list[str] = []

    report = await command.watch_canary(
        _configuration(),
        max_attempts=3,
        readiness_provider=_unused_provider,  # type: ignore[arg-type]
        capture_provider=_unused_provider,  # type: ignore[arg-type]
        demo_transport_provider=_unused_provider,  # type: ignore[arg-type]
        artifact_root=tmp_path / ".operator-artifacts",
        clock_ms=fake_time.clock_ms,
        monotonic=fake_time.monotonic,
        sleeper=fake_time.sleep,
        progress=progress.append,
        local_kill_switch=KillSwitch(),
    )

    assert report.status == "WATCH_EXHAUSTED"
    assert report.attempts == 3
    assert report.reason_codes == (
        "decision_hold",
        "watch_attempt_limit_reached",
    )
    assert prepared == 3
    assert len(sampled_at) == 3
    assert [value % 60_000 for value in sampled_at] == [10_000, 2_500, 2_500]
    assert fake_time.delays == [52.5, 60.0]
    assert [json.loads(item)["status"] for item in progress] == [
        "WAITING",
        "NO_ACTION",
        "WAITING",
        "NO_ACTION",
        "WAITING",
        "NO_ACTION",
    ]


def test_main_prompts_once_and_stops_at_first_ready_for_immediate_dry_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_time = FakeTime()
    prompts: list[str] = []
    capture_calls = 0
    dry_calls = 0
    output: list[str] = []

    async def capture(*args: object, **kwargs: object) -> CanaryCaptureReport:
        nonlocal capture_calls
        del args, kwargs
        capture_calls += 1
        return _capture(capture_calls)

    async def dry_run(*args: object, **kwargs: object):
        nonlocal dry_calls
        del args, kwargs
        dry_calls += 1
        return await _dry_run_result()

    def credential(prompt: str) -> str:
        prompts.append(prompt)
        return "vst-key" if "API key" in prompt else "vst-secret"

    monkeypatch.setattr(command, "capture_canary_inputs", capture)
    monkeypatch.setattr(command, "_prepare_capture", lambda *args, **kwargs: _ready())
    monkeypatch.setattr(command, "_dry_run_prepared", dry_run)

    assert command.main(
        ["--attempts", "5"],
        credential_provider=credential,
        readiness_provider=_unused_provider,  # type: ignore[arg-type]
        capture_provider=_unused_provider,  # type: ignore[arg-type]
        demo_transport_provider=_unused_provider,  # type: ignore[arg-type]
        output=output.append,
        clock_ms=fake_time.clock_ms,
        monotonic=fake_time.monotonic,
        sleeper=fake_time.sleep,
        artifact_root=tmp_path / ".operator-artifacts",
    ) == 0

    assert prompts == ["BingX VST API key: ", "BingX VST API secret: "]
    assert capture_calls == dry_calls == 1
    assert fake_time.delays == []
    final = json.loads(output[-1])
    assert final["status"] == DemoOrderStatus.DRY_RUN_READY.value
    assert final["attempts"] == 1
    rendered = "".join(output)
    assert "vst-key" not in rendered
    assert "vst-secret" not in rendered


@pytest.mark.asyncio
async def test_marketable_limit_retries_at_next_boundary_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_time = FakeTime()
    capture_calls = 0
    dry_calls = 0

    async def capture(*args: object, **kwargs: object) -> CanaryCaptureReport:
        nonlocal capture_calls
        del args, kwargs
        capture_calls += 1
        return _capture(capture_calls)

    async def dry_run(*args: object, **kwargs: object):
        nonlocal dry_calls
        del args, kwargs
        dry_calls += 1
        if dry_calls == 1:
            raise DemoCanaryError("marketable_limit_price")
        return await _dry_run_result()

    monkeypatch.setattr(command, "capture_canary_inputs", capture)
    monkeypatch.setattr(command, "_prepare_capture", lambda *args, **kwargs: _ready())
    monkeypatch.setattr(command, "_dry_run_prepared", dry_run)
    progress: list[str] = []

    report = await command.watch_canary(
        _configuration(),
        max_attempts=2,
        readiness_provider=_unused_provider,  # type: ignore[arg-type]
        capture_provider=_unused_provider,  # type: ignore[arg-type]
        demo_transport_provider=_unused_provider,  # type: ignore[arg-type]
        artifact_root=tmp_path / ".operator-artifacts",
        clock_ms=fake_time.clock_ms,
        monotonic=fake_time.monotonic,
        sleeper=fake_time.sleep,
        progress=progress.append,
        local_kill_switch=KillSwitch(),
    )

    assert report.status == DemoOrderStatus.DRY_RUN_READY.value
    assert report.attempts == 2
    assert capture_calls == dry_calls == 2
    assert fake_time.delays == [52.5]
    assert any(
        json.loads(item)["reason_codes"] == ["marketable_limit_price"]
        for item in progress
    )


@pytest.mark.asyncio
async def test_hard_capture_failure_stops_without_retry_or_dry_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_time = FakeTime()
    prepared = 0
    dried = 0

    async def capture(*args: object, **kwargs: object) -> CanaryCaptureReport:
        del args, kwargs
        raise CanaryCaptureError(
            "authentication_rejected",
            selected_host=VST_HOST,
        )

    def prepare(*args: object, **kwargs: object) -> IntentPreparationReport:
        nonlocal prepared
        del args, kwargs
        prepared += 1
        return _hold()

    async def dry_run(*args: object, **kwargs: object):
        nonlocal dried
        del args, kwargs
        dried += 1
        return await _dry_run_result()

    monkeypatch.setattr(command, "capture_canary_inputs", capture)
    monkeypatch.setattr(command, "_prepare_capture", prepare)
    monkeypatch.setattr(command, "_dry_run_prepared", dry_run)

    report = await command.watch_canary(
        _configuration(),
        max_attempts=5,
        readiness_provider=_unused_provider,  # type: ignore[arg-type]
        capture_provider=_unused_provider,  # type: ignore[arg-type]
        demo_transport_provider=_unused_provider,  # type: ignore[arg-type]
        artifact_root=tmp_path / ".operator-artifacts",
        clock_ms=fake_time.clock_ms,
        monotonic=fake_time.monotonic,
        sleeper=fake_time.sleep,
        progress=lambda _value: None,
        local_kill_switch=KillSwitch(),
    )

    assert report.status == "BLOCKED"
    assert report.attempts == 1
    assert report.selected_host == VST_HOST
    assert report.reason_codes == ("authentication_rejected",)
    assert prepared == dried == 0
    assert fake_time.delays == []


@pytest.mark.asyncio
async def test_network_phase_is_cancelled_at_the_watch_deadline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_time = FakeTime()
    cancelled = False

    async def capture(*args: object, **kwargs: object) -> CanaryCaptureReport:
        nonlocal cancelled
        del args, kwargs
        try:
            await command.asyncio.sleep(10)
        finally:
            cancelled = True
        return _capture()

    monkeypatch.setattr(command, "_MAX_SECONDS_PER_ATTEMPT", 0.01)
    monkeypatch.setattr(command, "capture_canary_inputs", capture)

    report = await command.watch_canary(
        _configuration(),
        max_attempts=1,
        readiness_provider=_unused_provider,  # type: ignore[arg-type]
        capture_provider=_unused_provider,  # type: ignore[arg-type]
        demo_transport_provider=_unused_provider,  # type: ignore[arg-type]
        artifact_root=tmp_path / ".operator-artifacts",
        clock_ms=fake_time.clock_ms,
        monotonic=fake_time.monotonic,
        sleeper=fake_time.sleep,
        progress=lambda _value: None,
        local_kill_switch=KillSwitch(),
    )

    assert report.status == "WATCH_EXHAUSTED"
    assert report.reason_codes == ("watch_duration_exceeded",)
    assert cancelled


@pytest.mark.asyncio
async def test_dry_run_uses_read_only_facade_and_closes_every_client(
    tmp_path: Path,
) -> None:
    public_callables = {
        name
        for name, value in vars(command._ReadOnlyDemoTransport).items()
        if callable(value) and not name.startswith("_")
    }
    assert public_callables == {
        "close",
        "fetch_balances",
        "fetch_constraints",
        "fetch_leverage",
        "fetch_open_orders",
        "fetch_orderbook",
        "fetch_position_mode",
        "fetch_positions",
        "fetch_recent_orders",
        "query_order",
    }
    assert {
        "submit_protected_limit",
        "cancel_order",
        "set_leverage",
        "set_position_mode",
        "transfer",
    }.isdisjoint(public_callables)

    artifact_root = tmp_path / ".operator-artifacts"
    prepared = _write_ready_artifact(artifact_root)
    readiness = ReadinessFake(server_time=NOW_MS)
    demo = FakeDemoTransport()

    report = await command._dry_run_prepared(
        _configuration(),
        prepared,
        artifact_root=artifact_root,
        readiness_provider=lambda _configuration: readiness,
        demo_transport_provider=lambda _configuration, _host: demo,
        clock_ms=lambda: NOW_MS,
        monotonic=lambda: 1.0,
    )

    assert report.status is DemoOrderStatus.DRY_RUN_READY
    assert readiness.closed and demo.closed
    call_names = [name for name, _arguments in demo.calls]
    assert "submit_protected_limit" not in call_names
    assert "cancel_order" not in call_names


@pytest.mark.asyncio
async def test_dry_run_preserves_final_host_and_primary_failure_when_close_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / ".operator-artifacts"
    prepared = _write_ready_artifact(artifact_root)
    readiness = ReadinessFake(server_time=NOW_MS)
    demo = FakeDemoTransport()
    demo.selected_host = "https://open-api-vst.bingx.pro"

    async def fail_plan(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise DemoCanaryError("marketable_limit_price")

    async def fail_close() -> None:
        demo.closed = True
        raise DemoCanaryError("transport_close_failed")

    monkeypatch.setattr(command, "build_demo_order_plan", fail_plan)
    monkeypatch.setattr(demo, "close", fail_close)

    with pytest.raises(command._DryRunFailure) as raised:
        await command._dry_run_prepared(
            _configuration(),
            prepared,
            artifact_root=artifact_root,
            readiness_provider=lambda _configuration: readiness,
            demo_transport_provider=lambda _configuration, _host: demo,
            clock_ms=lambda: NOW_MS,
            monotonic=lambda: 1.0,
        )

    assert raised.value.reason_code == "marketable_limit_price"
    assert raised.value.selected_host == demo.selected_host
    assert readiness.closed and demo.closed


def test_parser_has_only_bounded_read_only_controls_and_rejects_production_host(
    tmp_path: Path,
) -> None:
    options = {
        option
        for action in command.build_parser()._actions
        for option in action.option_strings
    }
    assert options == {"-h", "--help", "--host", "--attempts"}
    assert {
        "--execute",
        "--plan-digest",
        "--submit",
        "--cancel",
        "--side",
        "--quantity",
        "--leverage",
        "--api-key",
        "--api-secret",
    }.isdisjoint(options)

    calls: list[str] = []
    output: list[str] = []
    assert command.main(
        ["--host", "https://open-api.bingx.com"],
        credential_provider=lambda _prompt: calls.append("credential") or "unused",
        readiness_provider=lambda _configuration: calls.append("readiness"),  # type: ignore[arg-type,return-value]
        capture_provider=lambda _configuration, _host: calls.append("capture"),  # type: ignore[arg-type,return-value]
        demo_transport_provider=lambda _configuration, _host: calls.append("demo"),  # type: ignore[arg-type,return-value]
        output=output.append,
        artifact_root=tmp_path / ".operator-artifacts",
    ) == 2
    assert calls == []
    assert json.loads(output[0])["reason_codes"] == ["host_not_vst"]


def test_cli_has_one_asyncio_run_and_import_is_side_effect_safe() -> None:
    source = Path(command.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "asyncio"
        and node.func.attr == "run"
    ]
    assert len(calls) == 1
    owner: str | None = None
    current: ast.AST | None = calls[0]
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = current.name
            break
    assert owner == "main"
    assert "execute_demo_order_plan" not in source
    for forbidden in (
        "threading",
        "subprocess",
        "create_task",
        "ensure_future",
        "TaskGroup",
        "dotenv",
        "getenv",
        "os.environ",
    ):
        assert forbidden not in source

    repository = Path(__file__).resolve().parents[3]
    code = "\n".join(
        (
            "import asyncio, socket, subprocess",
            "def blocked(*args, **kwargs): raise AssertionError('side effect')",
            "socket.create_connection = blocked",
            "socket.socket.connect = blocked",
            "subprocess.Popen = blocked",
            "import scripts.bingx_vst_watch_canary",
        )
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
