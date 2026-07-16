from __future__ import annotations

from dataclasses import dataclass

from src.core.dependency_injection.container import Container
from src.core.registry.registry import Registry


@dataclass(slots=True)
class AppContext:
    """
    Shared application context.
    """

    container: Container
    registry: Registry