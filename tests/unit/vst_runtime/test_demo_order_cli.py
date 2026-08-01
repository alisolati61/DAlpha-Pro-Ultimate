from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

import scripts.bingx_vst_demo_order as command
from src.exchange.models import BingXBalance
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
    DemoContractConstraints,
    DemoLeverageSnapshot,
    DemoOrderPlan,
    DemoTopOfBook,
)
from src.vst_runtime.models import RemoteOrder, RemoteOrderStatus

NOW = 2_000_000_000_000


def _intent() -> ExecutionIntent:
    quantity = Decimal("0.01")
    return ExecutionIntent(
        intent_id="intent-canary",
        decision_id="decision-canary",
        status=IntentStatus.READY,
        symbol="BTC-USDT",
        exchange="bingx",
        timeframe="1h",
        entry=OrderSpecification(
            IntentSide.BUY,
            IntentOrderType.LIMIT,
            Decimal("100"),
            quantity,
            IntentTimeInForce.GTC,
            False,
        ),
        stop_loss=OrderSpecification(
            IntentSide.SELL,
            IntentOrderType.STOP,
            Decimal("90"),
            quantity,
            IntentTimeInForce.GTC,
            True,
        ),
        take_profit=OrderSpecification(
            IntentSide.SELL,
            IntentOrderType.TAKE_PROFIT,
            Decimal("120"),
            quantity,
            IntentTimeInForce.GTC,
            True,
        ),
        strategy_id="strategy-canary",
        strategy_version="v1",
        risk_amount=Decimal("1"),
        constraints_id="constraints-canary",
        source_timestamp=datetime.fromtimestamp(NOW / 1_000, tz=UTC),
        reason_codes=(IntentReason.INTENT_READY,),
    )


def _write_intent(tmp_path: Path) -> tuple[Path, str]:
    serialized = _intent().to_json()
    path = tmp_path / "intent.json"
    path.write_text(serialized, encoding="utf-8")
    return path, hashlib.sha256(serialized.encode()).hexdigest()


class ReadinessFake:
    def __init__(self, *, server_time: int = NOW) -> None:
        self.server_time = server_time
        self.selected_host = "https://open-api-vst.bingx.com"
        self.calls: list[str] = []
        self.closed = False

    async def fetch_server_time(self) -> int:
        self.calls.append("server_time")
        return self.server_time

    async def fetch_balance(self) -> tuple[BingXBalance, ...]:
        self.calls.append("balance")
        return (BingXBalance("VST", 100, 0, 100, 100, 100),)

    async def fetch_positions(self) -> tuple[()]:
        self.calls.append("positions")
        return ()

    async def close(self) -> None:
        self.calls.append("close")
        self.closed = True


class DemoFake:
    selected_host = "https://open-api-vst.bingx.com"

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.closed = False
        self.order: RemoteOrder | None = None

    async def fetch_constraints(self, symbol: str) -> DemoContractConstraints:
        self.calls.append("constraints")
        return DemoContractConstraints(
            symbol,
            Decimal("0.1"),
            Decimal("0.001"),
            Decimal("0.001"),
            Decimal("1"),
            20,
            20,
            True,
        )

    async def fetch_orderbook(self, symbol: str) -> DemoTopOfBook:
        self.calls.append("orderbook")
        return DemoTopOfBook(symbol, Decimal("100"), Decimal("101"), "1")

    async def fetch_balances(self) -> tuple[BingXBalance, ...]:
        self.calls.append("balances")
        return (BingXBalance("VST", 100, 0, 100, 100, 100),)

    async def fetch_positions(self, symbol: str) -> tuple[()]:
        self.calls.append("positions")
        return ()

    async def fetch_leverage(self, symbol: str) -> DemoLeverageSnapshot:
        self.calls.append("leverage")
        return DemoLeverageSnapshot(symbol, 2, 2)

    async def fetch_position_mode(self) -> str:
        self.calls.append("position_mode")
        return "HEDGE"

    async def fetch_open_orders(self, symbol: str) -> tuple[RemoteOrder, ...]:
        self.calls.append("open_orders")
        if self.order and self.order.status in {
            RemoteOrderStatus.NEW,
            RemoteOrderStatus.PARTIALLY_FILLED,
        }:
            return (self.order,)
        return ()

    async def fetch_recent_orders(self, symbol: str) -> tuple[RemoteOrder, ...]:
        self.calls.append("recent_orders")
        return ()

    async def submit_protected_limit(self, plan: DemoOrderPlan) -> RemoteOrder:
        self.calls.append("submit")
        self.order = RemoteOrder(
            plan.client_order_id,
            "remote-canary",
            plan.symbol,
            plan.side,
            "LIMIT",
            RemoteOrderStatus.NEW,
            plan.quantity,
            Decimal(0),
            Decimal(0),
            plan.limit_price,
            "1",
            NOW,
        )
        return self.order

    async def query_order(
        self,
        symbol: str,
        client_order_id: str,
    ) -> RemoteOrder | None:
        self.calls.append("query")
        return self.order

    async def cancel_order(
        self,
        symbol: str,
        client_order_id: str,
    ) -> RemoteOrder | None:
        self.calls.append("cancel")
        assert self.order is not None
        self.order = RemoteOrder(
            self.order.client_order_id,
            self.order.order_id,
            self.order.symbol,
            self.order.side,
            self.order.order_type,
            RemoteOrderStatus.CANCELED,
            self.order.original_quantity,
            self.order.filled_quantity,
            self.order.average_price,
            self.order.price,
            "2",
            NOW,
        )
        return self.order

    async def close(self) -> None:
        self.calls.append("close")
        self.closed = True


def _credentials(prompt: str) -> str:
    return {
        "BingX VST API key: ": "hidden-key",
        "BingX VST API secret: ": "hidden-secret",
    }[prompt]


def test_default_cli_is_dry_run_hidden_and_zero_write(tmp_path: Path) -> None:
    path, digest = _write_intent(tmp_path)
    readiness = ReadinessFake()
    demo = DemoFake()
    prompts: list[str] = []
    output: list[str] = []

    def credential_provider(prompt: str) -> str:
        prompts.append(prompt)
        return _credentials(prompt)

    assert command.main(
        ["--intent-file", str(path), "--intent-digest", digest],
        credential_provider=credential_provider,
        readiness_provider=lambda _: readiness,
        demo_transport_provider=lambda _configuration, _host: demo,
        output=output.append,
        clock_ms=lambda: NOW,
    ) == 0
    report = json.loads(output[0])
    assert report["status"] == "DRY_RUN_READY"
    assert report["plan"]["order_type"] == "LIMIT"
    assert "submit" not in demo.calls
    assert "cancel" not in demo.calls
    assert readiness.closed and demo.closed
    assert prompts == ["BingX VST API key: ", "BingX VST API secret: "]
    rendered = output[0] + repr(report)
    assert "hidden-key" not in rendered
    assert "hidden-secret" not in rendered
    for forbidden in (
        "api_key",
        "api_secret",
        "available_balance",
        "margin_balance",
        "wallet_balance",
        "signature",
        "signed_query",
        "raw_response",
    ):
        assert forbidden not in rendered


def test_production_host_rejected_before_input_credentials_or_factories() -> None:
    calls: list[str] = []
    output: list[str] = []

    assert command.main(
        [
            "--intent-file",
            "missing.json",
            "--intent-digest",
            "0" * 64,
            "--host",
            "https://open-api.bingx.com",
        ],
        credential_provider=lambda _: calls.append("credential") or "not-used",
        readiness_provider=lambda _: calls.append("readiness"),  # type: ignore[arg-type,return-value]
        demo_transport_provider=lambda _configuration, _host: calls.append("demo"),  # type: ignore[arg-type,return-value]
        output=output.append,
        clock_ms=lambda: NOW,
    ) == 2
    assert calls == []
    assert json.loads(output[0])["reason_codes"] == ["host_not_vst"]


def test_readiness_failure_prevents_demo_composition_and_write(tmp_path: Path) -> None:
    path, digest = _write_intent(tmp_path)
    readiness = ReadinessFake(server_time=NOW + 10_000)
    calls: list[str] = []
    output: list[str] = []

    assert command.main(
        ["--intent-file", str(path), "--intent-digest", digest],
        credential_provider=_credentials,
        readiness_provider=lambda _: readiness,
        demo_transport_provider=lambda _configuration, _host: calls.append("demo"),  # type: ignore[arg-type,return-value]
        output=output.append,
        clock_ms=lambda: NOW,
    ) == 2
    assert calls == []
    assert readiness.closed
    assert json.loads(output[0])["status"] == "BLOCKED"


def test_blank_credentials_fail_before_any_transport(tmp_path: Path) -> None:
    path, digest = _write_intent(tmp_path)
    for supplied in ((" ",), ("hidden-key", "")):
        values = iter(supplied)
        calls: list[str] = []
        output: list[str] = []

        def credential_provider(
            _: str, iterator: Iterator[str] = values
        ) -> str:
            return next(iterator)

        def readiness_provider(
            _: object, ledger: list[str] = calls
        ) -> None:
            ledger.append("readiness")

        def demo_provider(
            _configuration: object,
            _host: str,
            ledger: list[str] = calls,
        ) -> None:
            ledger.append("demo")

        assert command.main(
            ["--intent-file", str(path), "--intent-digest", digest],
            credential_provider=credential_provider,
            readiness_provider=readiness_provider,  # type: ignore[arg-type]
            demo_transport_provider=demo_provider,  # type: ignore[arg-type]
            output=output.append,
            clock_ms=lambda: NOW,
        ) == 2
        assert calls == []
        assert json.loads(output[0])["reason_codes"] == ["credential_required"]


def test_plan_failure_closes_both_clients_without_write(tmp_path: Path) -> None:
    path, digest = _write_intent(tmp_path)
    readiness = ReadinessFake()

    class BlockedDemoFake(DemoFake):
        async def fetch_constraints(
            self, symbol: str
        ) -> DemoContractConstraints:
            value = await super().fetch_constraints(symbol)
            return DemoContractConstraints(
                value.symbol,
                value.price_tick,
                value.quantity_step,
                value.minimum_quantity,
                value.minimum_notional,
                value.maximum_long_leverage,
                value.maximum_short_leverage,
                False,
            )

    demo = BlockedDemoFake()
    output: list[str] = []
    assert command.main(
        ["--intent-file", str(path), "--intent-digest", digest],
        credential_provider=_credentials,
        readiness_provider=lambda _: readiness,
        demo_transport_provider=lambda _configuration, _host: demo,
        output=output.append,
        clock_ms=lambda: NOW,
    ) == 2
    assert readiness.closed and demo.closed
    assert "submit" not in demo.calls and "cancel" not in demo.calls
    assert json.loads(output[0])["reason_codes"] == ["unsupported_symbol"]


def test_execute_requires_rebuilt_digest_before_prompt_or_write(
    tmp_path: Path,
) -> None:
    path, digest = _write_intent(tmp_path)
    readiness = ReadinessFake()
    demo = DemoFake()
    calls: list[str] = []
    output: list[str] = []

    assert command.main(
        [
            "--intent-file",
            str(path),
            "--intent-digest",
            digest,
            "--execute",
            "--plan-digest",
            "0" * 64,
        ],
        credential_provider=_credentials,
        confirmation_provider=lambda _: calls.append("confirm") or "yes",
        readiness_provider=lambda _: readiness,
        demo_transport_provider=lambda _configuration, _host: demo,
        output=output.append,
        clock_ms=lambda: NOW,
    ) == 2
    assert calls == []
    assert "submit" not in demo.calls
    assert demo.closed
    assert json.loads(output[0])["reason_codes"] == ["plan_digest_mismatch"]


def test_exact_two_step_execution_submits_once_and_closes(tmp_path: Path) -> None:
    path, intent_digest = _write_intent(tmp_path)
    dry_output: list[str] = []
    assert command.main(
        ["--intent-file", str(path), "--intent-digest", intent_digest],
        credential_provider=_credentials,
        readiness_provider=lambda _: ReadinessFake(),
        demo_transport_provider=lambda _configuration, _host: DemoFake(),
        output=dry_output.append,
        clock_ms=lambda: NOW,
    ) == 0
    dry = json.loads(dry_output[0])
    plan_digest = dry["plan"]["digest"]
    client_id = dry["plan"]["client_order_id"]

    readiness = ReadinessFake()
    demo = DemoFake()
    execute_output: list[str] = []
    assert command.main(
        [
            "--intent-file",
            str(path),
            "--intent-digest",
            intent_digest,
            "--execute",
            "--plan-digest",
            plan_digest,
        ],
        credential_provider=_credentials,
        confirmation_provider=lambda _: f"SUBMIT {client_id}",
        readiness_provider=lambda _: readiness,
        demo_transport_provider=lambda _configuration, _host: demo,
        output=execute_output.append,
        clock_ms=lambda: NOW,
    ) == 0
    report = json.loads(execute_output[0])
    assert report["status"] == "RECONCILED"
    assert report["transitions"] == ["SUBMITTED", "CANCELLED", "RECONCILED"]
    assert demo.calls.count("submit") == 1
    assert demo.calls.count("cancel") == 1
    # Plan preflight, immediate pre-submit duplicate guard, post-submit, and
    # post-cancel authoritative reads.
    assert demo.calls.count("query") == 4
    assert readiness.closed and demo.closed


def test_parser_has_no_credentials_or_direct_order_bypass_flags() -> None:
    options = {
        option
        for action in command.build_parser()._actions
        for option in action.option_strings
    }
    assert {
        "--api-key",
        "--api-secret",
        "--symbol",
        "--side",
        "--quantity",
        "--price",
        "--market",
        "--leverage",
    }.isdisjoint(options)


def test_unknown_credential_like_argument_is_not_echoed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []
    output: list[str] = []
    assert command.main(
        ["--api-secret", "hidden-secret"],
        credential_provider=lambda _: calls.append("credential") or "not-used",
        output=output.append,
        clock_ms=lambda: NOW,
    ) == 2
    captured = capsys.readouterr()
    rendered = "".join(output) + captured.out + captured.err
    assert calls == []
    assert "hidden-secret" not in rendered
    assert json.loads(output[0])["reason_codes"] == ["invalid_arguments"]


def test_cli_contains_exactly_one_asyncio_run_at_main_boundary() -> None:
    root = Path(command.__file__).resolve()
    source = root.read_text(encoding="utf-8")
    assert "dotenv" not in source
    assert "getenv" not in source
    assert "environ" not in source
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
    current: ast.AST | None = calls[0]
    owner: str | None = None
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = current.name
            break
    assert owner == "main"


def test_import_is_network_and_process_safe() -> None:
    repository = Path(__file__).resolve().parents[3]
    code = "\n".join(
        (
            "import asyncio, socket, subprocess",
            "def blocked(*args, **kwargs): raise AssertionError('side effect')",
            "socket.create_connection = blocked",
            "socket.socket.connect = blocked",
            "subprocess.Popen = blocked",
            "import scripts.bingx_vst_demo_order",
            "import src.vst_runtime.demo_order",
            "import src.vst_runtime.demo_transport",
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
