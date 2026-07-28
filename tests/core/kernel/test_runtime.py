"""Lifecycle tests for the side-effect-free application runtime."""

from __future__ import annotations

import pytest

from src.core.config.loader import load_runtime_config
from src.core.context.context_builder import ContextBuilder
from src.core.dependency_injection.exceptions import ServiceNotFound
from src.core.event_bus.event_bus import EventBus
from src.core.kernel.kernel import Kernel
from src.core.kernel.runtime import ApplicationRuntime, RuntimeMode
from src.core.kernel.state import KernelState
from src.core.lifecycle.lifecycle import LifecycleManager
from src.core.lifecycle.service import Service
from src.core.services.errors import MissingServiceDependencyError
from src.core.services.models import ServiceDefinition, ServiceState


class RecordingService(Service):
    def __init__(
        self,
        name: str,
        events: list[str],
        *,
        fail_initialize: bool = False,
        fail_start: bool = False,
        fail_stop: bool = False,
    ) -> None:
        self.name = name
        self.events = events
        self.fail_initialize = fail_initialize
        self.fail_start = fail_start
        self.fail_stop = fail_stop

    def initialize(self) -> None:
        self.events.append(f"initialize:{self.name}")

        if self.fail_initialize:
            raise RuntimeError(f"initialize failed: {self.name}")

    def start(self) -> None:
        self.events.append(f"start:{self.name}")

        if self.fail_start:
            raise RuntimeError(f"start failed: {self.name}")

    def stop(self) -> None:
        self.events.append(f"stop:{self.name}")

        if self.fail_stop:
            raise RuntimeError(f"stop failed: {self.name}")


def make_runtime(
    definitions: tuple[ServiceDefinition, ...] = (),
) -> ApplicationRuntime:
    return ApplicationRuntime(
        mode=RuntimeMode.DOCTOR,
        kernel=Kernel(),
        context=ContextBuilder.build(),
        event_bus=EventBus(),
        lifecycle_manager=LifecycleManager(),
        service_definitions=definitions,
    )


def define(
    service_id: str,
    service: Service,
    dependencies: tuple[str, ...] = (),
) -> ServiceDefinition:
    return ServiceDefinition(service_id, service, dependencies)


def test_runtime_retains_exact_validated_config() -> None:
    config = load_runtime_config(
        overrides={"environment": "test"}
    )
    runtime = ApplicationRuntime(
        mode=RuntimeMode.DOCTOR,
        config=config,
        kernel=Kernel(),
        context=ContextBuilder.build(),
        event_bus=EventBus(),
        lifecycle_manager=LifecycleManager(),
    )

    assert runtime.config is config
    assert not hasattr(runtime, "exchange")
    assert not hasattr(runtime, "execution")


@pytest.mark.asyncio
async def test_runtime_startup_is_idempotent() -> None:
    events: list[str] = []
    runtime = make_runtime(
        (define("local", RecordingService("local", events)),)
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
        (define("local", RecordingService("local", events)),)
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
            define("first", RecordingService("first", events)),
            define(
                "second",
                RecordingService("second", events),
                ("first",),
            ),
        )
    )
    await runtime.startup()

    await runtime.shutdown()

    assert events[-2:] == [
        "stop:second",
        "stop:first",
    ]


@pytest.mark.asyncio
async def test_dependency_order_overrides_registration_order() -> None:
    events: list[str] = []
    runtime = make_runtime(
        (
            define(
                "dependent",
                RecordingService("dependent", events),
                ("root",),
            ),
            define("root", RecordingService("root", events)),
        )
    )

    await runtime.startup()
    await runtime.shutdown()

    assert events == [
        "initialize:root",
        "initialize:dependent",
        "start:root",
        "start:dependent",
        "stop:dependent",
        "stop:root",
    ]


@pytest.mark.asyncio
async def test_invalid_graph_prevents_all_lifecycle_calls() -> None:
    events: list[str] = []
    runtime = make_runtime(
        (
            define(
                "worker",
                RecordingService("worker", events),
                ("missing",),
            ),
        )
    )

    with pytest.raises(MissingServiceDependencyError):
        await runtime.startup()

    assert events == []
    assert runtime.kernel.state is KernelState.SHUTDOWN
    assert runtime.shutdown_complete is True


@pytest.mark.asyncio
async def test_partial_startup_rolls_back() -> None:
    events: list[str] = []
    runtime = make_runtime(
        (
            define("first", RecordingService("first", events)),
            define(
                "broken",
                RecordingService(
                    "broken",
                    events,
                    fail_initialize=True,
                ),
            ),
            define("later", RecordingService("later", events)),
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
    assert (
        runtime.lifecycle_manager.state_of("broken")
        is ServiceState.FAILED
    )
    assert (
        runtime.lifecycle_manager.state_of("later")
        is ServiceState.CREATED
    )
    assert runtime.kernel.state is KernelState.SHUTDOWN
    assert runtime.shutdown_complete is True


@pytest.mark.asyncio
async def test_shutdown_reports_errors_after_all_cleanups() -> None:
    events: list[str] = []
    runtime = make_runtime(
        (
            define(
                "first",
                RecordingService(
                    "first",
                    events,
                    fail_stop=True,
                ),
            ),
            define(
                "second",
                RecordingService(
                    "second",
                    events,
                    fail_stop=True,
                ),
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


@pytest.mark.asyncio
async def test_start_failure_rolls_back_owned_services_once() -> None:
    events: list[str] = []
    runtime = make_runtime(
        (
            define("first", RecordingService("first", events)),
            define(
                "broken",
                RecordingService(
                    "broken",
                    events,
                    fail_start=True,
                ),
                ("first",),
            ),
            define(
                "later",
                RecordingService("later", events),
                ("broken",),
            ),
        )
    )

    with pytest.raises(RuntimeError, match="start failed: broken"):
        await runtime.startup()

    assert "start:later" not in events
    assert events[-3:] == [
        "stop:later",
        "stop:broken",
        "stop:first",
    ]
    assert runtime.kernel.state is KernelState.SHUTDOWN
    assert runtime.shutdown_complete is True

    await runtime.shutdown()
    assert events.count("stop:first") == 1


@pytest.mark.asyncio
async def test_original_and_rollback_failures_are_aggregated() -> None:
    events: list[str] = []
    runtime = make_runtime(
        (
            define(
                "first",
                RecordingService(
                    "first",
                    events,
                    fail_stop=True,
                ),
            ),
            define(
                "broken",
                RecordingService(
                    "broken",
                    events,
                    fail_initialize=True,
                ),
            ),
        )
    )

    with pytest.raises(BaseExceptionGroup) as captured:
        await runtime.startup()

    assert len(captured.value.exceptions) == 2
    assert "initialize failed: broken" in str(
        captured.value.exceptions[0]
    )
    assert "stop failed: first" in str(
        captured.value.exceptions[1]
    )


@pytest.mark.asyncio
async def test_failed_startup_clears_all_local_state() -> None:
    runtime = make_runtime(
        (
            define(
                "broken",
                RecordingService(
                    "broken",
                    [],
                    fail_initialize=True,
                ),
            ),
        )
    )
    runtime.context.registry.register("local", object())
    runtime.context.container.register(str, lambda: "local")
    runtime.event_bus.subscribe("local", lambda event: None)

    with pytest.raises(RuntimeError):
        await runtime.startup()

    assert runtime.context.registry.size == 0
    with pytest.raises(ServiceNotFound):
        runtime.context.container.resolve(str)
    assert runtime.event_bus.listener_count("local") == 0


@pytest.mark.asyncio
async def test_shutdown_runtime_cannot_restart() -> None:
    runtime = make_runtime()
    await runtime.startup()
    await runtime.shutdown()

    with pytest.raises(RuntimeError, match="cannot be restarted"):
        await runtime.startup()
