"""Lifecycle tests for the side-effect-free application runtime."""

from __future__ import annotations

import pytest

from src.core.context.context_builder import ContextBuilder
from src.core.event_bus.event_bus import EventBus
from src.core.kernel.kernel import Kernel
from src.core.kernel.runtime import ApplicationRuntime, RuntimeMode
from src.core.kernel.state import KernelState
from src.core.lifecycle.lifecycle import LifecycleManager
from src.core.lifecycle.service import Service


class RecordingService(Service):
    def __init__(
        self,
        name: str,
        events: list[str],
        *,
        fail_initialize: bool = False,
        fail_stop: bool = False,
    ) -> None:
        self.name = name
        self.events = events
        self.fail_initialize = fail_initialize
        self.fail_stop = fail_stop

    def initialize(self) -> None:
        self.events.append(f"initialize:{self.name}")

        if self.fail_initialize:
            raise RuntimeError(f"initialize failed: {self.name}")

    def start(self) -> None:
        self.events.append(f"start:{self.name}")

    def stop(self) -> None:
        self.events.append(f"stop:{self.name}")

        if self.fail_stop:
            raise RuntimeError(f"stop failed: {self.name}")


def make_runtime(
    services: tuple[Service, ...] = (),
) -> ApplicationRuntime:
    return ApplicationRuntime(
        mode=RuntimeMode.DOCTOR,
        kernel=Kernel(),
        context=ContextBuilder.build(),
        event_bus=EventBus(),
        lifecycle_manager=LifecycleManager(),
        services=services,
    )


@pytest.mark.asyncio
async def test_runtime_startup_is_idempotent() -> None:
    events: list[str] = []
    runtime = make_runtime(
        (RecordingService("local", events),)
    )

    await runtime.startup()
    await runtime.startup()

    assert events == [
        "initialize:local",
        "start:local",
    ]
    assert runtime.started is True
    assert runtime.kernel.state is KernelState.RUNNING


@pytest.mark.asyncio
async def test_runtime_shutdown_is_idempotent() -> None:
    events: list[str] = []
    runtime = make_runtime(
        (RecordingService("local", events),)
    )
    await runtime.startup()

    await runtime.shutdown()
    await runtime.shutdown()

    assert events.count("stop:local") == 1
    assert runtime.shutdown_complete is True
    assert runtime.kernel.state is KernelState.SHUTDOWN


@pytest.mark.asyncio
async def test_runtime_shutdown_uses_reverse_order() -> None:
    events: list[str] = []
    runtime = make_runtime(
        (
            RecordingService("first", events),
            RecordingService("second", events),
        )
    )
    await runtime.startup()

    await runtime.shutdown()

    assert events[-2:] == [
        "stop:second",
        "stop:first",
    ]


@pytest.mark.asyncio
async def test_partial_startup_rolls_back() -> None:
    events: list[str] = []
    runtime = make_runtime(
        (
            RecordingService("first", events),
            RecordingService(
                "broken",
                events,
                fail_initialize=True,
            ),
        )
    )

    with pytest.raises(
        RuntimeError,
        match="initialize failed: broken",
    ):
        await runtime.startup()

    assert events == [
        "initialize:first",
        "initialize:broken",
        "stop:first",
    ]
    assert runtime.kernel.state is KernelState.SHUTDOWN
    assert runtime.shutdown_complete is True


@pytest.mark.asyncio
async def test_shutdown_reports_errors_after_all_cleanups() -> None:
    events: list[str] = []
    runtime = make_runtime(
        (
            RecordingService(
                "first",
                events,
                fail_stop=True,
            ),
            RecordingService(
                "second",
                events,
                fail_stop=True,
            ),
        )
    )
    await runtime.startup()

    with pytest.raises(BaseExceptionGroup) as captured:
        await runtime.shutdown()

    assert events[-2:] == [
        "stop:second",
        "stop:first",
    ]
    assert len(captured.value.exceptions) == 2
    assert runtime.kernel.state is KernelState.SHUTDOWN
