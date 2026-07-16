from abc import ABC, abstractmethod

from typing import Any


class IConfiguration(ABC):

    @abstractmethod
    def get(self, key: str) -> Any:
        ...

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        ...