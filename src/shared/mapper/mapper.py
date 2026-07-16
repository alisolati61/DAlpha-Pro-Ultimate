from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

S = TypeVar("S")
D = TypeVar("D")


class Mapper(ABC, Generic[S, D]):

    @abstractmethod
    def map(self, source: S) -> D:
        ...