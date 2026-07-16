from __future__ import annotations

from src.core.registry.exceptions import (
    AlreadyRegisteredError,
    NotRegisteredError,
)
from src.core.registry.types import RegistryObject


class Registry:
    """
    Central object registry.

    Stores shared services/components.
    """

    def __init__(self) -> None:
        self._objects: dict[str, RegistryObject] = {}

    def register(self, name: str, obj: RegistryObject) -> None:
        if name in self._objects:
            raise AlreadyRegisteredError(name)

        self._objects[name] = obj

    def get(self, name: str) -> RegistryObject:
        if name not in self._objects:
            raise NotRegisteredError(name)

        return self._objects[name]

    def exists(self, name: str) -> bool:
        return name in self._objects

    def unregister(self, name: str) -> None:
        if name not in self._objects:
            raise NotRegisteredError(name)

        del self._objects[name]

    def clear(self) -> None:
        self._objects.clear()

    @property
    def size(self) -> int:
        return len(self._objects)