from __future__ import annotations

from abc import ABC, abstractmethod

from typing import Any


class IRegistry(ABC):

    @abstractmethod
    def register(self, name: str, obj: Any) -> None:
        ...

    @abstractmethod
    def get(self, name: str) -> Any:
        ...

    @abstractmethod
    def exists(self, name: str) -> bool:
        ...