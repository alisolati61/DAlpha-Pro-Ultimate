"""Tests for the safe Doctor-only command-line interface."""

from __future__ import annotations

import runpy
import socket
from pathlib import Path

import httpx
import pytest
import websockets

import src.cli as cli


def _metadata_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli.metadata,
        "version",
        lambda distribution_name: "0.1.0",
    )


def test_default_cli_command_is_doctor(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _metadata_available(monkeypatch)

    assert cli.main([]) == 0
    assert "Doctor: OK" in capsys.readouterr().out


def test_explicit_doctor_command_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _metadata_available(monkeypatch)

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

    _metadata_available(monkeypatch)
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
