"""Deterministic, local-only Doctor diagnostics."""

from __future__ import annotations

import inspect
import math
import sys
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from importlib import metadata
from time import monotonic
from typing import Any, TypeAlias

from src.core.config.loader import load_runtime_config
from src.core.config.models import RuntimeConfig
from src.core.diagnostics.models import (
    DiagnosticCheck,
    DiagnosticReport,
    DiagnosticStatus,
    sanitize_public_message,
)
from src.core.kernel.bootstrap import build_runtime
from src.core.kernel.kernel import Kernel
from src.core.kernel.runtime import ApplicationRuntime, RuntimeMode
from src.core.kernel.state import KernelState

_DISTRIBUTION_NAME = "alpha-pro-x-infinity"
_MINIMUM_PYTHON = (3, 12)
_UNKNOWN_VERSION = "unknown"

Clock: TypeAlias = Callable[[], datetime]
Timer: TypeAlias = Callable[[], float]
RuntimeFactory: TypeAlias = Callable[[RuntimeConfig], ApplicationRuntime]
CheckAction: TypeAlias = Callable[
    [],
    bool | Awaitable[bool],
]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class DoctorRunner:
    """Execute safe local checks in a stable order."""

    def __init__(
        self,
        *,
        runtime_factory: RuntimeFactory = build_runtime,
        config: RuntimeConfig | None = None,
        clock: Clock = _utc_now,
        timer: Timer = monotonic,
        python_version: tuple[int, ...] | None = None,
        version_reader: Callable[[str], str] = metadata.version,
    ) -> None:
        for callback, name in (
            (runtime_factory, "runtime_factory"),
            (clock, "clock"),
            (timer, "timer"),
            (version_reader, "version_reader"),
        ):
            if not callable(callback):
                raise TypeError(f"{name} must be callable.")

        self._runtime_factory = runtime_factory
        self._config = (
            load_runtime_config()
            if config is None
            else config
        )
        if not isinstance(self._config, RuntimeConfig):
            raise TypeError("config must be a RuntimeConfig.")
        self._clock = clock
        self._timer = timer
        self._python_version = (
            tuple(sys.version_info[:3])
            if python_version is None
            else tuple(python_version)
        )
        self._version_reader = version_reader

    async def run(self) -> DiagnosticReport:
        """Return a complete report while isolating every check failure."""

        report_started_at = self._clock()
        report_timer_started = self._timer()
        checks: list[DiagnosticCheck] = []
        package_version = _UNKNOWN_VERSION
        runtime: ApplicationRuntime | None = None

        check, _ = await self._run_check(
            "python",
            lambda: self._python_version >= _MINIMUM_PYTHON,
            passed_message="Python requirement satisfied.",
            failed_message="Python 3.12 or newer is required.",
        )
        checks.append(check)

        def read_metadata() -> bool:
            nonlocal package_version
            candidate = self._version_reader(
                _DISTRIBUTION_NAME
            ).strip()
            sanitized = sanitize_public_message(candidate)

            if not candidate or sanitized != candidate:
                package_version = _UNKNOWN_VERSION
                return False

            package_version = sanitized
            return True

        check, _ = await self._run_check(
            "package metadata",
            read_metadata,
            passed_message="Package metadata is available.",
            failed_message="Package metadata is unavailable.",
        )
        checks.append(check)

        check, _ = await self._run_check(
            "kernel construction",
            lambda: isinstance(Kernel(), Kernel),
            passed_message="Kernel construction succeeded.",
            failed_message="Kernel construction failed safely.",
        )
        checks.append(check)

        def construct_runtime() -> bool:
            nonlocal runtime
            candidate = self._runtime_factory(self._config)

            if not isinstance(candidate, ApplicationRuntime):
                return False

            runtime = candidate
            return (
                runtime.mode is RuntimeMode.DOCTOR
                and runtime.config is self._config
            )

        check, _ = await self._run_check(
            "runtime construction",
            construct_runtime,
            passed_message="Doctor runtime construction succeeded.",
            failed_message="Doctor runtime construction failed safely.",
        )
        checks.append(check)

        check, _ = await self._run_check(
            "exchange wiring absent",
            lambda: (
                runtime is not None
                and not hasattr(runtime, "exchange")
            ),
            passed_message="Exchange wiring is absent.",
            failed_message="Exchange wiring safety check failed.",
        )
        checks.append(check)

        check, _ = await self._run_check(
            "execution wiring absent",
            lambda: (
                runtime is not None
                and not hasattr(runtime, "execution")
            ),
            passed_message="Execution wiring is absent.",
            failed_message="Execution wiring safety check failed.",
        )
        checks.append(check)

        async def startup_runtime() -> bool:
            if runtime is None:
                return False

            await runtime.startup()
            return runtime.kernel.state is KernelState.RUNNING

        check, _ = await self._run_check(
            "local startup",
            startup_runtime,
            passed_message="Local startup succeeded.",
            failed_message="Local startup failed safely.",
        )
        checks.append(check)

        async def shutdown_runtime() -> bool:
            if runtime is None:
                return False

            await runtime.shutdown()
            return runtime.kernel.state is KernelState.SHUTDOWN

        check, _ = await self._run_check(
            "local shutdown",
            shutdown_runtime,
            passed_message="Local shutdown succeeded.",
            failed_message="Local shutdown failed safely.",
        )
        checks.append(check)

        report_finished_at = self._clock()
        report_duration = self._elapsed_ms(
            report_timer_started,
            self._timer(),
        )
        frozen_checks = tuple(checks)

        return DiagnosticReport(
            application=self._config.application_name,
            version=package_version or _UNKNOWN_VERSION,
            mode=RuntimeMode.DOCTOR.value,
            success=all(
                check.status is DiagnosticStatus.PASS
                for check in frozen_checks
            ),
            started_at=report_started_at,
            finished_at=report_finished_at,
            duration_ms=report_duration,
            checks=frozen_checks,
        )

    async def _run_check(
        self,
        name: str,
        action: CheckAction,
        *,
        passed_message: str,
        failed_message: str,
    ) -> tuple[DiagnosticCheck, bool]:
        started = self._timer()
        passed = False

        try:
            result: Any = action()

            if inspect.isawaitable(result):
                result = await result

            passed = result is True
        except BaseException:
            passed = False

        duration_ms = self._elapsed_ms(started, self._timer())
        return (
            DiagnosticCheck(
                name=name,
                status=(
                    DiagnosticStatus.PASS
                    if passed
                    else DiagnosticStatus.FAIL
                ),
                message=(
                    passed_message
                    if passed
                    else failed_message
                ),
                duration_ms=duration_ms,
            ),
            passed,
        )

    @staticmethod
    def _elapsed_ms(started: float, finished: float) -> float:
        if (
            isinstance(started, bool)
            or isinstance(finished, bool)
            or not isinstance(started, (int, float))
            or not isinstance(finished, (int, float))
        ):
            return 0.0

        duration = (float(finished) - float(started)) * 1000.0

        if not math.isfinite(duration) or duration < 0:
            return 0.0

        return duration


__all__ = ("DoctorRunner",)
