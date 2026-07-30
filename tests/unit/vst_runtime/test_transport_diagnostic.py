from __future__ import annotations

import inspect
import json
from typing import Any

import scripts.bingx_vst_transport_diagnostic as command


def diagnostic(**changes: Any) -> dict[str, object]:
    value: dict[str, object] = {
        "attempted_host": "https://open-api-vst.bingx.com",
        "transport_stage": "complete",
        "exception_type": None,
        "sanitized_errno": None,
        "reason_code": "ok",
        "server_time_ms": 123,
    }
    value.update(changes)
    return value


def test_parser_and_main_have_no_credential_boundary() -> None:
    parser = command.build_parser()
    options = {option for action in parser._actions for option in action.option_strings}
    assert "--api-key" not in options
    assert "--api-secret" not in options
    assert "credential" not in inspect.signature(command.main).parameters


def test_public_diagnostic_prints_only_sanitized_result(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    calls: list[tuple[str, float]] = []

    async def fake(host: str, timeout: float) -> dict[str, object]:
        calls.append((host, timeout))
        return diagnostic()

    monkeypatch.setattr(command, "_diagnose", fake)
    assert command.main([]) == 0
    assert calls == [("https://open-api-vst.bingx.com", 10.0)]
    output = json.loads(capsys.readouterr().out)
    assert output == diagnostic()


def test_production_host_is_rejected_before_transport(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    calls: list[str] = []

    async def forbidden(host: str, timeout: float) -> dict[str, object]:
        calls.append(host)
        return diagnostic()

    monkeypatch.setattr(command, "_diagnose", forbidden)
    assert command.main(["--host", "https://open-api.bingx.com"]) == 2
    assert calls == []
    output = capsys.readouterr().out
    assert "diagnostic_configuration_invalid" in output
    assert "open-api.bingx.com" not in output
