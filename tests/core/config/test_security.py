"""Security and side-effect guards for the configuration boundary."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.core.config.loader import load_runtime_config


def test_serialization_is_deterministic_and_safe(
    tmp_path: Path,
) -> None:
    config = load_runtime_config(
        overrides={
            "application_name": "api_key=hidden",
            "data_directory": tmp_path / "private-data",
            "state_directory": Path("token-secret"),
        }
    )

    first = config.to_json()
    second = config.to_json()
    payload = json.loads(first)

    assert first == second
    assert payload == config.to_dict()
    assert payload["application_name"] == "<withheld>"
    assert payload["data_directory"] == "<absolute-path>"
    assert payload["state_directory"] == "<withheld>"
    assert "hidden" not in first.casefold()
    assert str(tmp_path).casefold() not in first.casefold()


def test_loader_never_reads_process_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPHA_PRO_X_ENVIRONMENT", "production")

    config = load_runtime_config()

    assert config.environment == "development"


def test_loader_does_not_access_dotenv_or_create_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "ALPHA_PRO_X_ENVIRONMENT=production",
        encoding="utf-8",
    )

    config = load_runtime_config(
        overrides={
            "data_directory": "new-data",
            "state_directory": "new-state",
            "diagnostics_output_directory": "new-reports",
        }
    )

    assert config.environment == "development"
    assert not (tmp_path / "new-data").exists()
    assert not (tmp_path / "new-state").exists()
    assert not (tmp_path / "new-reports").exists()


def test_config_imports_are_side_effect_free(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[3]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project_root)
    script = (
        "import sys;"
        "import src.core.config;"
        "from src.core.config import load_runtime_config;"
        "load_runtime_config();"
        "blocked=('src.config.settings','src.logger.logger',"
        "'src.exchange','src.execution.execution_engine');"
        "assert not any(name in sys.modules for name in blocked)"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "logs").exists()
    assert tuple(tmp_path.iterdir()) == ()


def test_loading_requires_no_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BINGX_API_KEY", raising=False)
    monkeypatch.delenv("BINGX_API_SECRET", raising=False)

    assert load_runtime_config().runtime_mode.value == "doctor"
