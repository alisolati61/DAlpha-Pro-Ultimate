from __future__ import annotations

from src.core.lifecycle.service import Service


class LifecycleManager:
    """
    Responsible for managing application services.
    """

    def __init__(self) -> None:
        self._services: list[Service] = []

    def register(self, service: Service) -> None:
        self._services.append(service)

    def initialize(self) -> None:
        for service in self._services:
            service.initialize()

    def start(self) -> None:
        for service in self._services:
            service.start()

    def stop(self) -> None:
        for service in reversed(self._services):
            service.stop()