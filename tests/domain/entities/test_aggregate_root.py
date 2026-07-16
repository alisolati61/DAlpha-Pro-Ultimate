from dataclasses import dataclass
from uuid import uuid4

from src.domain.entities import AggregateRoot
from src.domain.events import DomainEvent


@dataclass(eq=False)
class FakeAggregate(AggregateRoot):
    pass


def test_add_event():

    aggregate = FakeAggregate(uuid4())

    aggregate.add_event(DomainEvent())

    events = aggregate.pull_events()

    assert len(events) == 1


def test_events_are_cleared():

    aggregate = FakeAggregate(uuid4())

    aggregate.add_event(DomainEvent())

    aggregate.pull_events()

    assert aggregate.pull_events() == []