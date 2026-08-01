from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

import scripts.bingx_vst_demo_order as demo_command
import scripts.bingx_vst_prepare_intent as command
from src.execution_intent.models import IntentStatus
from src.vst_runtime.demo_order import (
    DemoCanaryError,
    DemoLeverageSnapshot,
    DemoTopOfBook,
    load_canonical_ready_intent,
)
from src.vst_runtime.intent_preparation import ARTIFACT_DIRECTORY_NAME
from tests.unit.vst_runtime.test_demo_order_cli import (
    DemoFake,
    ReadinessFake,
    _credentials,
)
from tests.unit.vst_runtime.test_intent_preparation import (
    NOW_MS,
    canonical,
    canonical_documents,
    serialized_documents,
)


def write_inputs(tmp_path: Path) -> list[str]:
    arguments: list[str] = []
    for name, content in serialized_documents().items():
        path = tmp_path / f"{name}.json"
        path.write_text(content, encoding="utf-8")
        digest = hashlib.sha256(content.encode()).hexdigest()
        arguments.extend(
            (f"--{name}-input", str(path), f"--{name}-digest", digest)
        )
    return arguments


class CompatibleDemoFake(DemoFake):
    async def fetch_orderbook(self, symbol: str) -> DemoTopOfBook:
        self.calls.append("orderbook")
        return DemoTopOfBook(
            symbol,
            Decimal("101"),
            Decimal("103"),
            "compatible-book",
        )

    async def fetch_leverage(self, symbol: str) -> DemoLeverageSnapshot:
        self.calls.append("leverage")
        return DemoLeverageSnapshot(symbol, 1, 1)


def prepared_artifact(
    tmp_path: Path,
) -> tuple[dict[str, object], Path, Path]:
    directory = tmp_path / ARTIFACT_DIRECTORY_NAME
    output: list[str] = []
    assert command.main(
        write_inputs(tmp_path),
        output=output.append,
        artifact_directory=directory,
        clock_ms=lambda: NOW_MS,
    ) == 0
    report = json.loads(output[0])
    relative = report["artifact_path"]
    assert isinstance(relative, str)
    return report, directory / Path(relative).name, directory


def test_cli_prepares_canonical_artifact_accepted_by_demo_loader_and_dry_run(
    tmp_path: Path,
) -> None:
    report, artifact, _directory = prepared_artifact(tmp_path)
    digest = report["intent_digest"]
    assert isinstance(digest, str)
    content = artifact.read_text(encoding="utf-8")
    assert hashlib.sha256(content.encode()).hexdigest() == digest
    intent, verified = load_canonical_ready_intent(content, digest)
    assert intent.status is IntentStatus.READY
    assert verified == digest

    readiness = ReadinessFake(server_time=NOW_MS)
    demo = CompatibleDemoFake()
    demo_output: list[str] = []
    assert demo_command.main(
        ["--intent-file", str(artifact), "--intent-digest", digest],
        credential_provider=_credentials,
        readiness_provider=lambda _: readiness,
        demo_transport_provider=lambda _configuration, _host: demo,
        output=demo_output.append,
        clock_ms=lambda: NOW_MS,
    ) == 0
    demo_report = json.loads(demo_output[0])
    assert demo_report["status"] == "DRY_RUN_READY"
    assert "submit" not in demo.calls
    assert "cancel" not in demo.calls
    assert readiness.closed and demo.closed


def test_tampered_prepared_artifact_is_rejected_before_credentials_or_network(
    tmp_path: Path,
) -> None:
    report, artifact, _directory = prepared_artifact(tmp_path)
    digest = report["intent_digest"]
    assert isinstance(digest, str)
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    payload["entry"]["quantity"] = "0.051"
    artifact.write_text(canonical(payload), encoding="utf-8")
    with pytest.raises(DemoCanaryError, match="intent_digest_mismatch"):
        load_canonical_ready_intent(artifact.read_text(encoding="utf-8"), digest)

    calls: list[str] = []
    output: list[str] = []
    assert demo_command.main(
        ["--intent-file", str(artifact), "--intent-digest", digest],
        credential_provider=lambda _: calls.append("credential") or "unused",
        readiness_provider=lambda _: calls.append("readiness"),  # type: ignore[arg-type,return-value]
        demo_transport_provider=lambda _configuration, _host: calls.append("demo"),  # type: ignore[arg-type,return-value]
        output=output.append,
        clock_ms=lambda: NOW_MS,
    ) == 2
    assert calls == []
    assert json.loads(output[0])["reason_codes"] == ["intent_digest_mismatch"]


@pytest.mark.parametrize(
    ("case", "expected_reason"),
    (
        ("unavailable", "input_unavailable"),
        ("wrong_directory", "artifact_directory_invalid"),
        ("sensitive", "invalid_account_input"),
    ),
)
def test_cli_failures_are_sanitized_and_create_no_artifact(
    tmp_path: Path,
    case: str,
    expected_reason: str,
) -> None:
    arguments = write_inputs(tmp_path)
    directory = tmp_path / ARTIFACT_DIRECTORY_NAME
    if case == "unavailable":
        arguments[1] = str(tmp_path / "private-secret-missing.json")
    elif case == "wrong_directory":
        directory = tmp_path / "wrong-artifact-directory"
    else:
        account_path = tmp_path / "account.json"
        account = canonical_documents()["account"]
        account["api_secret"] = "fake-private-secret"
        account_path.write_text(canonical(account), encoding="utf-8")
    output: list[str] = []

    assert command.main(
        arguments,
        output=output.append,
        artifact_directory=directory,
        clock_ms=lambda: NOW_MS,
    ) == 2
    rendered = output[0]
    assert json.loads(rendered)["reason_codes"] == [expected_reason]
    assert "private-secret" not in rendered
    assert not directory.exists()


def test_parser_exposes_only_canonical_local_input_files() -> None:
    options = {
        option
        for action in command.build_parser()._actions
        for option in action.option_strings
    }
    assert options == {
        "-h",
        "--help",
        "--market-input",
        "--market-digest",
        "--account-input",
        "--account-digest",
        "--constraints-input",
        "--constraints-digest",
        "--policy-input",
        "--policy-digest",
    }
    assert {
        "--api-key",
        "--api-secret",
        "--credential",
        "--host",
        "--execute",
        "--symbol",
        "--side",
        "--quantity",
        "--price",
        "--leverage",
        "--artifact-directory",
    }.isdisjoint(options)


def test_unknown_sensitive_argument_is_not_echoed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output: list[str] = []
    assert command.main(
        ["--api-secret", "fake-private-secret"],
        output=output.append,
        artifact_directory=tmp_path / ARTIFACT_DIRECTORY_NAME,
        clock_ms=lambda: NOW_MS,
    ) == 2
    captured = capsys.readouterr()
    rendered = "".join(output) + captured.out + captured.err
    assert "fake-private-secret" not in rendered
    assert json.loads(output[0])["reason_codes"] == ["invalid_arguments"]


def test_cli_output_is_deterministic_idempotent_and_account_value_free(
    tmp_path: Path,
) -> None:
    arguments = write_inputs(tmp_path)
    directory = tmp_path / ARTIFACT_DIRECTORY_NAME
    first: list[str] = []
    second: list[str] = []
    assert command.main(
        arguments,
        output=first.append,
        artifact_directory=directory,
        clock_ms=lambda: NOW_MS,
    ) == 0
    assert command.main(
        arguments,
        output=second.append,
        artifact_directory=directory,
        clock_ms=lambda: NOW_MS,
    ) == 0
    assert first == second
    assert first[0] == canonical(json.loads(first[0]))
    assert len(tuple(directory.glob("*.json"))) == 1
    for forbidden in (
        "available_balance",
        "current_exposure",
        "equity",
        "portfolio",
        "used_margin",
        "api_key",
        "api_secret",
    ):
        assert forbidden not in first[0]


def test_wrong_source_digest_and_wrong_final_digest_are_rejected(
    tmp_path: Path,
) -> None:
    arguments = write_inputs(tmp_path)
    market_digest_index = arguments.index("--market-digest") + 1
    arguments[market_digest_index] = "0" * 64
    output: list[str] = []
    directory = tmp_path / ARTIFACT_DIRECTORY_NAME
    assert command.main(
        arguments,
        output=output.append,
        artifact_directory=directory,
        clock_ms=lambda: NOW_MS,
    ) == 2
    assert json.loads(output[0])["reason_codes"] == [
        "market_input_digest_mismatch"
    ]
    assert not directory.exists()

    valid_root = tmp_path / "valid"
    valid_root.mkdir()
    report, artifact, _directory = prepared_artifact(valid_root)
    content = artifact.read_text(encoding="utf-8")
    with pytest.raises(DemoCanaryError, match="intent_digest_mismatch"):
        load_canonical_ready_intent(content, "0" * 64)
    assert report["status"] == IntentStatus.READY.value


def test_operator_artifact_directory_is_git_ignored() -> None:
    repository = Path(__file__).resolve().parents[3]
    ignore_lines = (repository / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert f"/{ARTIFACT_DIRECTORY_NAME}/" in ignore_lines


def test_cli_import_is_socket_process_and_filesystem_safe(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[3]
    code = "\n".join(
        (
            "import asyncio, socket, subprocess",
            "from pathlib import Path",
            "def blocked(*args, **kwargs): raise AssertionError('side effect')",
            "socket.create_connection = blocked",
            "socket.socket.connect = blocked",
            "subprocess.Popen = blocked",
            "import scripts.bingx_vst_prepare_intent",
            "import src.vst_runtime.intent_preparation",
            f"assert not Path({str(tmp_path / ARTIFACT_DIRECTORY_NAME)!r}).exists()",
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


def test_preparation_cli_has_no_async_network_or_environment_boundary() -> None:
    source = Path(command.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "asyncio" not in imported_names
    assert "socket" not in imported_names
    assert "subprocess" not in imported_names
    assert "dotenv" not in source
    assert "getenv" not in source
    assert "environ" not in source
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        for node in ast.walk(tree)
    )
