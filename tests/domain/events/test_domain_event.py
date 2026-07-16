from src.domain.events import DomainEvent


def test_event_creation():

    event = DomainEvent()

    assert event.event_id is not None

    assert event.occurred_at is not None