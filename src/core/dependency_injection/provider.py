from dataclasses import dataclass

from typing import Any, Callable

from src.core.dependency_injection.lifetime import ServiceLifetime


@dataclass(slots=True)
class ServiceProvider:

    factory: Callable[[], Any]

    lifetime: ServiceLifetime

    instance: Any = None