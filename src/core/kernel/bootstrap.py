"""Safe factories for application runtimes."""

from __future__ import annotations

from src.core.context.context_builder import ContextBuilder
from src.core.event_bus.event_bus import EventBus
from src.core.kernel.kernel import Kernel
from src.core.kernel.runtime import ApplicationRuntime, RuntimeMode
from src.core.lifecycle.lifecycle import LifecycleManager


def build_runtime(
    mode: RuntimeMode = RuntimeMode.DOCTOR,
) -> ApplicationRuntime:
    """Build an unstarted, local-only runtime without external side effects."""

    if not isinstance(mode, RuntimeMode):
        raise TypeError("mode must be a RuntimeMode.")

    return ApplicationRuntime(
        mode=mode,
        kernel=Kernel(),
        context=ContextBuilder.build(),
        event_bus=EventBus(),
        lifecycle_manager=LifecycleManager(),
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
