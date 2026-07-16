from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.events import DomainEvent

from .base_entity import BaseEntity


@dataclass(eq=False, slots=True)
class AggregateRoot(BaseEntity):

    _events: list[DomainEvent] = field(
        default_factory=list,
        init=False,
        repr=False,
    )

    def add_event(
        self,
        event: DomainEvent,
    ) -> None:

        self._events.append(event)

    def pull_events(self) -> list[DomainEvent]:

        events = self._events.copy()

        self._events.clear()

        return events