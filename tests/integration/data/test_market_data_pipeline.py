"""Runtime integration tests for explicit Market Data service wiring."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.core.diagnostics.doctor import DoctorRunner
from src.core.diagnostics.models import DiagnosticStatus
from src.core.kernel.bootstrap import build_runtime
from src.core.services.errors import MissingServiceDependencyError
from src.core.services.models import ServiceDefinition, ServiceState
from src.data.errors import DataServiceUnavailableError
from src.data.market_data import MarketData
from src.data.service import MARKET_DATA_SERVICE_ID, MarketDataService

EXPECTED_CHECKS = (
    "python",
    "package metadata",
    "kernel construction",
    "runtime construction",
    "exchange wiring absent",
    "execution wiring absent",
    "local startup",
    "local shutdown",
)


def snapshot() -> MarketData:
    return MarketData(
        symbol="BTCUSDT",
        exchange="local",
        timeframe="1m",
        price=100,
        bid=99,
        ask=101,
        volume=1,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_explicit_runtime_service_pipeline_and_shutdown() -> None:
    service = MarketDataService()
    definition = ServiceDefinition(MARKET_DATA_SERVICE_ID, service)
    runtime = build_runtime(service_definitions=(definition,))

    with pytest.raises(DataServiceUnavailableError):
        service.ingest_snapshot(snapshot())

    await runtime.startup()
    accepted = service.ingest_snapshot(snapshot())

    assert accepted is snapshot() or accepted == snapshot()
    assert runtime.lifecycle_manager.state_of(
        MARKET_DATA_SERVICE_ID
    ) is ServiceState.RUNNING

    await runtime.shutdown()

    assert runtime.lifecycle_manager.state_of(
        MARKET_DATA_SERVICE_ID
    ) is ServiceState.STOPPED
    assert service.snapshot_count == 0
    with pytest.raises(DataServiceUnavailableError):
        service.ingest_snapshot(snapshot())


@pytest.mark.asyncio
async def test_build_runtime_does_not_create_data_service_automatically() -> None:
    runtime = build_runtime()

    assert runtime.service_definitions == ()
    assert not hasattr(runtime, "market_data_service")

    await runtime.startup()
    await runtime.shutdown()


@pytest.mark.asyncio
async def test_invalid_graph_prevents_data_lifecycle_calls() -> None:
    class TrackingService(MarketDataService):
        initialize_calls = 0

        def initialize(self) -> None:
            self.initialize_calls += 1
            super().initialize()

    service = TrackingService()
    definition = ServiceDefinition(
        MARKET_DATA_SERVICE_ID,
        service,
        ("missing-local-service",),
    )
    runtime = build_runtime(service_definitions=(definition,))

    with pytest.raises(MissingServiceDependencyError):
        await runtime.startup()

    assert service.initialize_calls == 0


@pytest.mark.asyncio
async def test_doctor_remains_zero_service_with_exact_checks() -> None:
    report = await DoctorRunner(
        version_reader=lambda name: "0.1.0"
    ).run()

    assert tuple(check.name for check in report.checks) == EXPECTED_CHECKS
    assert all(
        check.status is DiagnosticStatus.PASS
        for check in report.checks
    )


def test_data_main_is_import_safe_and_not_a_second_cli(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[3]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project_root)
    script = (
        "import asyncio,sys;"
        "before=set(asyncio.all_tasks(asyncio.new_event_loop()));"
        "import src.data.main as module;"
        "service=module.create_market_data_service();"
        "assert not hasattr(module,'main');"
        "assert service.snapshot_count == 0;"
        "blocked=('src.exchange','src.execution.execution_engine');"
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
    assert tuple(tmp_path.iterdir()) == ()
