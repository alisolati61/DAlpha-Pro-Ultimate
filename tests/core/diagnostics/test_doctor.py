"""Behavioral tests for deterministic safe Doctor diagnostics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.core.config.loader import load_runtime_config
from src.core.config.models import RuntimeConfig
from src.core.context.context_builder import ContextBuilder
from src.core.diagnostics.doctor import DoctorRunner
from src.core.diagnostics.models import DiagnosticStatus
from src.core.event_bus.event_bus import EventBus
from src.core.kernel.kernel import Kernel
from src.core.kernel.runtime import ApplicationRuntime, RuntimeMode
from src.core.lifecycle.lifecycle import LifecycleManager
from src.core.lifecycle.service import Service

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


class IncrementingTimer:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        current = self.value
        self.value += 0.001
        return current


class SequenceClock:
    def __init__(self) -> None:
        self.values = iter(
            (
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(
                    2026,
                    1,
                    1,
                    tzinfo=UTC,
                )
                + timedelta(milliseconds=17),
            )
        )

    def __call__(self) -> datetime:
        return next(self.values)


class FailingStartupService(Service):
    def initialize(self) -> None:
        raise RuntimeError(
            "api_key=hidden C:\\private\\failure"
        )

    def start(self) -> None:
        raise AssertionError("start must not run")

    def stop(self) -> None:
        return None


class ShutdownTrackingRuntime(ApplicationRuntime):
    def __init__(self, config: RuntimeConfig) -> None:
        super().__init__(
            mode=RuntimeMode.DOCTOR,
            config=config,
            kernel=Kernel(),
            context=ContextBuilder.build(),
            event_bus=EventBus(),
            lifecycle_manager=LifecycleManager(),
            services=(FailingStartupService(),),
        )
        self.shutdown_calls = 0

    async def shutdown(self) -> None:
        self.shutdown_calls += 1
        await super().shutdown()


@pytest.mark.asyncio
async def test_doctor_report_is_complete_and_deterministic() -> None:
    report = await DoctorRunner(
        timer=IncrementingTimer(),
        clock=SequenceClock(),
        python_version=(3, 12, 0),
        version_reader=lambda name: "0.1.0",
    ).run()

    assert tuple(check.name for check in report.checks) == EXPECTED_CHECKS
    assert all(
        check.status is DiagnosticStatus.PASS
        for check in report.checks
    )
    assert report.application == "Alpha Pro X Infinity"
    assert report.version == "0.1.0"
    assert report.mode == "doctor"
    assert report.success is True
    assert report.duration_ms == pytest.approx(17.0)


@pytest.mark.asyncio
async def test_check_exceptions_are_isolated_and_sanitized() -> None:
    def fail_metadata(name: str) -> str:
        raise RuntimeError(
            "password=hidden /home/private/project"
        )

    report = await DoctorRunner(
        version_reader=fail_metadata,
    ).run()
    checks = {
        check.name: check
        for check in report.checks
    }

    assert checks["package metadata"].status is DiagnosticStatus.FAIL
    assert checks["kernel construction"].status is DiagnosticStatus.PASS
    assert checks["local shutdown"].status is DiagnosticStatus.PASS
    assert report.success is False

    public_payload = report.to_json().casefold()
    assert "hidden" not in public_payload
    assert "/home/" not in public_payload
    assert "traceback" not in public_payload
    assert "runtimeerror" not in public_payload


@pytest.mark.asyncio
async def test_unsafe_metadata_version_is_not_exposed() -> None:
    report = await DoctorRunner(
        version_reader=lambda name: "api_key=hidden",
    ).run()

    assert report.checks[1].status is DiagnosticStatus.FAIL
    assert report.version == "unknown"
    assert "hidden" not in report.to_json().casefold()


@pytest.mark.asyncio
async def test_shutdown_is_attempted_after_startup_failure() -> None:
    config = load_runtime_config()
    runtime = ShutdownTrackingRuntime(config)

    report = await DoctorRunner(
        config=config,
        runtime_factory=lambda supplied: runtime,
        version_reader=lambda name: "0.1.0",
    ).run()
    checks = {
        check.name: check
        for check in report.checks
    }

    assert checks["local startup"].status is DiagnosticStatus.FAIL
    assert checks["local shutdown"].status is DiagnosticStatus.PASS
    assert runtime.shutdown_calls == 1
    assert report.success is False


@pytest.mark.asyncio
async def test_doctor_passes_exact_config_to_runtime() -> None:
    config = load_runtime_config(
        overrides={"environment": "test"}
    )
    received: list[RuntimeConfig] = []

    def factory(supplied: RuntimeConfig) -> ApplicationRuntime:
        received.append(supplied)
        return ApplicationRuntime(
            mode=supplied.runtime_mode,
            config=supplied,
            kernel=Kernel(),
            context=ContextBuilder.build(),
            event_bus=EventBus(),
            lifecycle_manager=LifecycleManager(),
        )

    report = await DoctorRunner(
        config=config,
        runtime_factory=factory,
        version_reader=lambda name: "0.1.0",
    ).run()

    assert report.success is True
    assert received == [config]


@pytest.mark.asyncio
async def test_failed_python_check_does_not_stop_later_checks() -> None:
    report = await DoctorRunner(
        python_version=(3, 11, 9),
        version_reader=lambda name: "0.1.0",
    ).run()

    assert report.checks[0].status is DiagnosticStatus.FAIL
    assert all(
        check.status is DiagnosticStatus.PASS
        for check in report.checks[1:]
    )
