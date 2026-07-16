from __future__ import annotations

from src.core.kernel.state import KernelState


class Kernel:
    """
    Central system kernel.

    Responsible only for
    - lifecycle
    - startup
    - shutdown
    - system state
    """

    def __init__(self) -> None:
        self._state = KernelState.CREATED

    @property
    def state(self) -> KernelState:
        return self._state

    def initialize(self) -> None:
        if self._state != KernelState.CREATED:
            raise RuntimeError("Kernel can only be initialized once.")

        self._state = KernelState.INITIALIZED

    def start(self) -> None:
        if self._state != KernelState.INITIALIZED:
            raise RuntimeError("Kernel must be initialized before start.")

        self._state = KernelState.RUNNING

    def stop(self) -> None:
        if self._state != KernelState.RUNNING:
            raise RuntimeError("Kernel is not running.")

        self._state = KernelState.STOPPED

    def shutdown(self) -> None:
        self._state = KernelState.SHUTDOWN