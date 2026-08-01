from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.bingx_vst_capture_canary_inputs as command
from src.vst_runtime.canary_capture import CanaryCaptureReport
from tests.unit.vst_runtime.test_canary_capture import (
    NOW_MS,
    CaptureFake,
    ReadinessFake,
)


def _credentials(prompt: str) -> str:
    return {
        "BingX VST API key: ": "fake-hidden-key",
        "BingX VST API secret: ": "fake-hidden-secret",
    }[prompt]


def test_production_host_is_rejected_before_credentials_transport_or_network(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    output: list[str] = []
    assert command.main(
        ["--host", "https://open-api.bingx.com"],
        credential_provider=lambda _prompt: calls.append("credential") or "unused",
        readiness_provider=lambda _configuration: calls.append(
            "readiness"
        ),  # type: ignore[arg-type,return-value]
        capture_provider=lambda _configuration, _host: calls.append(
            "capture"
        ),  # type: ignore[arg-type,return-value]
        output=output.append,
        clock_ms=lambda: NOW_MS,
        artifact_root=tmp_path / ".operator-artifacts",
    ) == 2
    assert calls == []
    assert json.loads(output[0])["reason_codes"] == ["host_not_vst"]
    assert not (tmp_path / ".operator-artifacts").exists()


def test_cli_hidden_credentials_success_output_and_commands_are_secret_free(
    tmp_path: Path,
) -> None:
    ledger: list[str] = []
    readiness = ReadinessFake(ledger)
    capture = CaptureFake(ledger)
    prompts: list[str] = []
    output: list[str] = []

    def credentials(prompt: str) -> str:
        prompts.append(prompt)
        return _credentials(prompt)

    assert command.main(
        [],
        credential_provider=credentials,
        readiness_provider=lambda _: readiness,
        capture_provider=lambda _configuration, _host: capture,
        output=output.append,
        clock_ms=lambda: NOW_MS,
        artifact_root=tmp_path / ".operator-artifacts",
    ) == 0
    assert prompts == ["BingX VST API key: ", "BingX VST API secret: "]
    rendered = output[0]
    report = json.loads(rendered)
    assert report["status"] == "CAPTURED"
    assert "bingx_vst_prepare_intent.py" in report["preparation_command"]
    assert "bingx_vst_demo_order.py" in report["dry_run_command"]
    assert "--execute" not in report["dry_run_command"]
    for forbidden in (
        "fake-hidden-key",
        "fake-hidden-secret",
        "available_balance",
        "wallet_balance",
        "used_margin",
        "signature",
        "X-BX-APIKEY",
    ):
        assert forbidden not in rendered
    assert readiness.closed and capture.closed


def test_cli_has_no_policy_symbol_credential_or_write_controls() -> None:
    options = {
        option
        for action in command.build_parser()._actions
        for option in action.option_strings
    }
    assert options == {
        "-h",
        "--help",
        "--configuration-version",
        "--host",
        "--maximum-clock-drift-ms",
    }
    assert {
        "--api-key",
        "--api-secret",
        "--credential-file",
        "--dotenv",
        "--symbol",
        "--side",
        "--quantity",
        "--price",
        "--leverage",
        "--risk-percent",
        "--maximum-notional",
        "--policy-file",
        "--execute",
        "--submit",
        "--cancel",
        "--transfer",
        "--withdraw",
        "--output-directory",
    }.isdisjoint(options)


def test_unknown_sensitive_argument_is_sanitized(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output: list[str] = []
    assert command.main(
        ["--api-secret", "fake-private-secret"],
        output=output.append,
        artifact_root=tmp_path / ".operator-artifacts",
        clock_ms=lambda: NOW_MS,
    ) == 2
    rendered = "".join(output) + capsys.readouterr().out + capsys.readouterr().err
    assert "fake-private-secret" not in rendered
    assert json.loads(output[0])["reason_codes"] == ["invalid_arguments"]


def test_blank_credential_fails_before_composition_and_prints_no_value(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    output: list[str] = []
    assert command.main(
        [],
        credential_provider=lambda prompt: (
            "fake-key" if "API key" in prompt else ""
        ),
        readiness_provider=lambda _configuration: calls.append(
            "readiness"
        ),  # type: ignore[arg-type,return-value]
        capture_provider=lambda _configuration, _host: calls.append(
            "capture"
        ),  # type: ignore[arg-type,return-value]
        output=output.append,
        artifact_root=tmp_path / ".operator-artifacts",
        clock_ms=lambda: NOW_MS,
    ) == 2
    assert calls == []
    assert json.loads(output[0])["reason_codes"] == ["credential_required"]
    assert "fake-key" not in output[0]


def test_cli_maps_unexpected_failure_to_stable_secret_free_report(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def unexpected(*args: object, **kwargs: object) -> CanaryCaptureReport:
        del args, kwargs
        raise RuntimeError("fake-hidden-secret signed=query")

    monkeypatch.setattr(command, "_run_capture", unexpected)
    output: list[str] = []
    assert command.main(
        [],
        credential_provider=_credentials,
        output=output.append,
        artifact_root=tmp_path / ".operator-artifacts",
        clock_ms=lambda: NOW_MS,
    ) == 2
    assert json.loads(output[0])["reason_codes"] == ["capture_runtime_failed"]
    assert "fake-hidden-secret" not in output[0]
    assert "signed=query" not in output[0]


def test_asyncio_run_exists_once_only_at_capture_cli_main_boundary() -> None:
    source = Path(command.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
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
    module_source = Path(
        "src/vst_runtime/canary_capture.py"
    ).read_text(encoding="utf-8")
    assert "asyncio.run" not in module_source
    assert "threading" not in module_source
    assert "subprocess" not in module_source


def test_cli_import_is_network_process_and_filesystem_safe(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[3]
    artifact = tmp_path / ".operator-artifacts"
    code = "\n".join(
        (
            "import asyncio, socket, subprocess",
            "from pathlib import Path",
            "def blocked(*args, **kwargs): raise AssertionError('side effect')",
            "socket.create_connection = blocked",
            "socket.socket.connect = blocked",
            "subprocess.Popen = blocked",
            "import scripts.bingx_vst_capture_canary_inputs",
            "import src.vst_runtime.canary_capture",
            f"assert not Path({str(artifact)!r}).exists()",
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


def test_cli_has_no_environment_dotenv_or_write_endpoint_access() -> None:
    script_source = Path(command.__file__).read_text(encoding="utf-8")
    module_source = Path("src/vst_runtime/canary_capture.py").read_text(
        encoding="utf-8"
    )
    combined = script_source + module_source
    for forbidden in (
        "dotenv",
        "getenv",
        "os.environ",
        "place_order",
        "submit_protected_limit",
        "cancel_order",
        "set_leverage",
        "set_margin_type",
        "set_position_mode",
        "close_all_positions",
        "withdraw",
        "transfer",
    ):
        assert forbidden not in combined
