"""Tests for the safe Doctor-only command-line interface."""

from __future__ import annotations

import json
import runpy
import socket
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import websockets

import src.cli as cli
from src.core.diagnostics.models import (
    DiagnosticCheck,
    DiagnosticReport,
    DiagnosticStatus,
)


def _report(
    *,
    success: bool = True,
) -> DiagnosticReport:
    status = (
        DiagnosticStatus.PASS
        if success
        else DiagnosticStatus.FAIL
    )
    now = datetime(2026, 1, 1, tzinfo=UTC)
    check = DiagnosticCheck(
        name="python",
        status=status,
        message=(
            "Python requirement satisfied."
            if success
            else "Python requirement failed."
        ),
        duration_ms=1,
    )
    return DiagnosticReport(
        application="Alpha Pro X Infinity",
        version="0.1.0",
        mode="doctor",
        success=success,
        started_at=now,
        finished_at=now,
        duration_ms=1,
        checks=(check,),
    )


def _stub_runner(
    monkeypatch: pytest.MonkeyPatch,
    report: DiagnosticReport,
) -> None:
    class StubRunner:
        async def run(self) -> DiagnosticReport:
            return report

    monkeypatch.setattr(cli, "DoctorRunner", StubRunner)


def test_default_cli_command_is_doctor(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _stub_runner(monkeypatch, _report())

    assert cli.main([]) == 0
    assert "Doctor: OK" in capsys.readouterr().out


def test_explicit_doctor_command_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _stub_runner(monkeypatch, _report())

    assert cli.main(["doctor"]) == 0
    assert "Doctor: OK" in capsys.readouterr().out


def test_unknown_cli_command_fails() -> None:
    with pytest.raises(SystemExit) as captured:
        cli.main(["live"])

    assert captured.value.code == 2


def test_doctor_does_not_open_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.exchange.base import BaseExchange
    from src.exchange.bingx_client import BingXHttpClient
    from src.exchange.ccxt_exchange import CCXTExchange
    from src.exchange.exchange_factory import ExchangeFactory
    from src.execution.execution_engine import ExecutionEngine

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("Doctor attempted a forbidden operation.")

    async def async_fail(
        *args: object,
        **kwargs: object,
    ) -> None:
        raise AssertionError("Doctor attempted a forbidden operation.")

    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(httpx.Client, "request", fail)
    monkeypatch.setattr(httpx.AsyncClient, "request", async_fail)
    monkeypatch.setattr(websockets, "connect", async_fail)
    monkeypatch.setattr(ExchangeFactory, "create", fail)
    monkeypatch.setattr(CCXTExchange, "connect", async_fail)
    monkeypatch.setattr(BaseExchange, "create_order", async_fail)
    monkeypatch.setattr(BingXHttpClient, "place_order", async_fail)
    monkeypatch.setattr(ExecutionEngine, "execute", fail)

    assert cli.main([]) == 0


def test_json_stdout_contains_json_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = _report()
    _stub_runner(monkeypatch, report)

    assert cli.main(["doctor", "--format", "json"]) == 0
    captured = capsys.readouterr()

    assert captured.err == ""
    assert json.loads(captured.out) == report.to_dict()


def test_output_writes_exact_payload_and_refuses_overwrite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = _report()
    _stub_runner(monkeypatch, report)
    output = tmp_path / "report.json"
    arguments = [
        "doctor",
        "--format",
        "json",
        "--output",
        str(output),
    ]

    assert cli.main(arguments) == 0
    assert output.read_text(encoding="utf-8") == report.to_json()
    assert capsys.readouterr().out == ""

    output.write_text("preserve", encoding="utf-8")

    assert cli.main(arguments) == 1
    assert output.read_text(encoding="utf-8") == "preserve"
    assert "output unavailable" in capsys.readouterr().err

    assert cli.main([*arguments, "--force"]) == 0
    assert output.read_text(encoding="utf-8") == report.to_json()


def test_failed_report_returns_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_runner(monkeypatch, _report(success=False))

    assert cli.main(["doctor"]) == 1


def test_force_without_output_is_argparse_misuse() -> None:
    with pytest.raises(SystemExit) as captured:
        cli.main(["doctor", "--force"])

    assert captured.value.code == 2


def test_output_write_failure_returns_one_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _stub_runner(monkeypatch, _report())
    missing_parent = tmp_path / "missing" / "report.json"

    assert cli.main(
        [
            "doctor",
            "--output",
            str(missing_parent),
        ]
    ) == 1
    captured = capsys.readouterr()

    assert "traceback" not in captured.err.casefold()
    assert "output unavailable" in captured.err


def test_root_main_delegates_to_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[()]] = []

    def fake_main() -> int:
        calls.append(())
        return 7

    monkeypatch.setattr(cli, "main", fake_main)
    root_main = Path(__file__).resolve().parents[1] / "main.py"

    with pytest.raises(SystemExit) as captured:
        runpy.run_path(
            str(root_main),
            run_name="__main__",
        )

    assert captured.value.code == 7
    assert calls == [()]
