from __future__ import annotations

from typing import Any

from src.core.dependency_injection.provider import ServiceProvider

from src.core.dependency_injection.lifetime import ServiceLifetime

from src.core.dependency_injection.exceptions import (
    ServiceAlreadyRegistered,
    ServiceNotFound,
)


class Container:

    def __init__(self):

        self._services: dict[type, ServiceProvider] = {}

    def register(
        self,
        interface: type,
        factory,
        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON,
    ):

        if interface in self._services:

            raise ServiceAlreadyRegistered(interface)

        self._services[interface] = ServiceProvider(
            factory=factory,
            lifetime=lifetime,
        )

    def resolve(self, interface: type) -> Any:

        if interface not in self._services:

            raise ServiceNotFound(interface)

        provider = self._services[interface]

        if provider.lifetime == ServiceLifetime.SINGLETON:

            if provider.instance is None:

                provider.instance = provider.factory()

            return provider.instance

        return provider.factory()

    def clear(self):

        self._services.clear()