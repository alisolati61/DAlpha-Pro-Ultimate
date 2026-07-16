from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class EntityId:
    value: UUID = field(default_factory=uuid4)

    @classmethod
    def from_string(cls, value: str) -> "EntityId":
        return cls(UUID(value))

    def __str__(self) -> str:
        return str(self.value)