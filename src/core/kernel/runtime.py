"""Side-effect-free application runtime for local operating modes."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Iterable

from src.core.context.app_context import AppContext
from src.core.event_bus.event_bus import EventBus
from src.core.kernel.kernel import Kernel
from src.core.kernel.state import KernelState
from src.core.lifecycle.lifecycle import LifecycleManager
from src.core.services.models import ServiceDefinition

if TYPE_CHECKING:
    from src.core.config.models import RuntimeConfig
    from src.core.lifecycle.service import Service


class RuntimeMode(str, Enum):
    """Explicitly supported application modes."""

    DOCTOR = "doctor"


class ApplicationRuntime:
    """Own local application components and coordinate their lifecycle."""

    def __init__(
        self,
        *,
        mode: RuntimeMode,
        kernel: Kernel,
        context: AppContext,
        event_bus: EventBus,
        lifecycle_manager: LifecycleManager,
        config: RuntimeConfig | None = None,
        service_definitions: Iterable[ServiceDefinition] = (),
        services: Iterable[Service] = (),
    ) -> None:
        from src.core.config.loader import load_runtime_config
        from src.core.config.models import RuntimeConfig

        if not isinstance(mode, RuntimeMode):
            raise TypeError("mode must be a RuntimeMode.")

        normalized_config = (
            load_runtime_config()
            if config is None
            else config
        )
        if not isinstance(normalized_config, RuntimeConfig):
            raise TypeError("config must be a RuntimeConfig.")
        if normalized_config.runtime_mode is not mode:
            raise ValueError("config runtime mode must match mode.")

        if not isinstance(kernel, Kernel):
            raise TypeError("kernel must be a Kernel.")

        if not isinstance(context, AppContext):
            raise TypeError("context must be an AppContext.")

        if not isinstance(event_bus, EventBus):
            raise TypeError("event_bus must be an EventBus.")

        if not isinstance(lifecycle_manager, LifecycleManager):
            raise TypeError(
                "lifecycle_manager must be a LifecycleManager."
            )

        normalized_definitions = tuple(service_definitions)
        legacy_services = tuple(services)

        if legacy_services:
            raise TypeError(
                "services require explicit ServiceDefinition objects."
            )

        if not all(
            isinstance(definition, ServiceDefinition)
            for definition in normalized_definitions
        ):
            raise TypeError(
                "service_definitions must contain ServiceDefinition objects."
            )

        self.mode = mode
        self.config = normalized_config
        self.kernel = kernel
        self.context = context
        self.event_bus = event_bus
        self.lifecycle_manager = lifecycle_manager
        self._started = False
        self._shutdown = False

        for definition in normalized_definitions:
            self.lifecycle_manager.register(definition)

        self.service_definitions = self.lifecycle_manager.definitions

    @property
    def started(self) -> bool:
        return self._started

    @property
    def shutdown_complete(self) -> bool:
        return self._shutdown

    async def startup(self) -> None:
        """Start local services once, rolling them back after partial failure."""

        if self._started:
            return

        if self._shutdown:
            raise RuntimeError("A shutdown runtime cannot be restarted.")

        try:
            self.lifecycle_manager.resolve()

            if self.kernel.state is KernelState.CREATED:
                self.kernel.initialize()

            if self.kernel.state is not KernelState.INITIALIZED:
                raise RuntimeError(
                    "Kernel must be created or initialized before startup."
                )

            self.lifecycle_manager.initialize()
            self.lifecycle_manager.start()
            self.kernel.start()
            self._started = True
        except BaseException as startup_error:
            rollback_errors = self._stop_services()
            self._clear_local_state(rollback_errors)
            self._shutdown_kernel(rollback_errors)
            self._started = False
            self._shutdown = True

            if rollback_errors:
                raise BaseExceptionGroup(
                    "Runtime startup and rollback failed.",
                    [startup_error, *rollback_errors],
                ) from startup_error

            raise

    async def shutdown(self) -> None:
        """Stop owned components once and report all cleanup failures."""

        if self._shutdown:
            return

        cleanup_errors = self._stop_services()
        self._shutdown_kernel(cleanup_errors)
        self._clear_local_state(cleanup_errors)

        self._started = False
        self._shutdown = True

        if cleanup_errors:
            raise BaseExceptionGroup(
                "Runtime shutdown failed.",
                cleanup_errors,
            )

    def _stop_services(self) -> list[BaseException]:
        errors: list[BaseException] = []

        try:
            self.lifecycle_manager.stop()
        except BaseExceptionGroup as error_group:
            errors.extend(error_group.exceptions)
        except BaseException as error:
            errors.append(error)
        return errors

    def _shutdown_kernel(
        self,
        errors: list[BaseException],
    ) -> None:
        if self.kernel.state is KernelState.RUNNING:
            try:
                self.kernel.stop()
            except BaseException as error:
                errors.append(error)

        try:
            self.kernel.shutdown()
        except BaseException as error:
            errors.append(error)

    def _clear_local_state(
        self,
        errors: list[BaseException],
    ) -> None:
        cleanup_actions = (
            self.event_bus.clear,
            self.context.container.clear,
            self.context.registry.clear,
        )

        for cleanup in cleanup_actions:
            try:
                cleanup()
            except BaseException as error:
                errors.append(error)


__all__ = (
    "ApplicationRuntime",
    "RuntimeMode",
)
