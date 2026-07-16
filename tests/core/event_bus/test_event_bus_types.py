from src.core.event_bus.event import Event
from src.core.event_bus.types import EventHandler


def test_handler_protocol_accepts_function():

    def callback(event: Event) -> None:
        pass

    handler: EventHandler = callback

    assert callable(handler)


def test_handler_receives_event():

    received = []

    def callback(event: Event) -> None:
        received.append(event.event_name)

    event = Event()

    callback(event)

    assert received == ["Event"]