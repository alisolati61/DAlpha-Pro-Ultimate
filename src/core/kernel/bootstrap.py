"""Safe factories for application runtimes."""

from __future__ import annotations

from collections.abc import Iterable

from src.core.config.loader import load_runtime_config
from src.core.config.models import RuntimeConfig
from src.core.context.context_builder import ContextBuilder
from src.core.event_bus.event_bus import EventBus
from src.core.kernel.kernel import Kernel
from src.core.kernel.runtime import ApplicationRuntime
from src.core.lifecycle.lifecycle import LifecycleManager
from src.core.services.models import ServiceDefinition


def build_runtime(
    config: RuntimeConfig | None = None,
    *,
    service_definitions: Iterable[ServiceDefinition] = (),
) -> ApplicationRuntime:
    """Build an unstarted, local-only runtime without external side effects."""

    normalized_config = (
        load_runtime_config()
        if config is None
        else config
    )
    if not isinstance(normalized_config, RuntimeConfig):
        raise TypeError("config must be a RuntimeConfig.")

    normalized_definitions = tuple(service_definitions)

    return ApplicationRuntime(
        mode=normalized_config.runtime_mode,
        config=normalized_config,
        kernel=Kernel(),
        context=ContextBuilder.build(),
        event_bus=EventBus(),
        lifecycle_manager=LifecycleManager(),
        service_definitions=normalized_definitions,
    )


def bootstrap() -> Kernel:
    """Preserve the original initialized-kernel compatibility helper."""

    runtime = build_runtime()
    runtime.kernel.initialize()
    return runtime.kernel


__all__ = (
    "bootstrap",
    "build_runtime",
)
