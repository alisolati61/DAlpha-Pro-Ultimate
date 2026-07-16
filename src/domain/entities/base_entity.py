from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from uuid import UUID


@dataclass(eq=False, slots=True)
class BaseEntity(ABC):
    id: UUID

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseEntity):
            return False

        return (
            self.__class__ is other.__class__
            and self.id == other.id
        )

    def __hash__(self) -> int:
        return hash((self.__class__, self.id))