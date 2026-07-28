"""Safety tests for the Doctor bootstrap factory."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.core.config.loader import load_runtime_config
from src.core.kernel.bootstrap import build_runtime
from src.core.kernel.runtime import RuntimeMode
from src.core.kernel.state import KernelState


def test_build_runtime_defaults_to_doctor() -> None:
    runtime = build_runtime()

    assert runtime.mode is RuntimeMode.DOCTOR
    assert runtime.kernel.state is KernelState.CREATED
    assert runtime.started is False


def test_build_runtime_retains_supplied_config() -> None:
    config = load_runtime_config(
        overrides={"environment": "test"}
    )

    runtime = build_runtime(config)

    assert runtime.config is config


@pytest.mark.asyncio
async def test_doctor_requires_no_api_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BINGX_API_KEY", raising=False)
    monkeypatch.delenv("BINGX_API_SECRET", raising=False)

    runtime = build_runtime()
    await runtime.startup()
    await runtime.shutdown()

    assert runtime.mode is RuntimeMode.DOCTOR
    assert runtime.shutdown_complete is True


def test_doctor_does_not_construct_exchange(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.exchange.exchange_factory import ExchangeFactory

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("Doctor constructed an exchange.")

    monkeypatch.setattr(ExchangeFactory, "create", fail)

    runtime = build_runtime()

    assert not hasattr(runtime, "exchange")


def test_doctor_does_not_construct_execution_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.execution.execution_engine import ExecutionEngine

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("Doctor constructed an execution engine.")

    monkeypatch.setattr(ExecutionEngine, "__init__", fail)

    runtime = build_runtime()

    assert not hasattr(runtime, "execution")


def test_safe_imports_have_no_external_side_effects(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[3]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project_root)
    environment.pop("BINGX_API_KEY", None)
    environment.pop("BINGX_API_SECRET", None)
    script = (
        "import sys;"
        "import src.cli;"
        "import src.core.kernel.bootstrap;"
        "import src.core.kernel.runtime;"
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
    assert not (tmp_path / "logs" / "alpha.log").exists()
