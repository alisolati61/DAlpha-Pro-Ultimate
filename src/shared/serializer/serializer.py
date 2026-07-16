from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Serializer(ABC):

    @abstractmethod
    def dumps(self, obj: Any) -> str:
        ...

    @abstractmethod
    def loads(self, data: str) -> Any:
        ...