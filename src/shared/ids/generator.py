from __future__ import annotations

from abc import ABC, abstractmethod

from .prefixes import IdPrefix


class IdGenerator(ABC):

    @abstractmethod
    def generate(self, prefix: IdPrefix) -> str:
        ...