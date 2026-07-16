from src.core.event_bus.event import Event
from src.core.event_bus.event_bus import EventBus


def test_publish():

    bus = EventBus()

    result = []

    def callback(event):

        result.append(event.event_name)

    bus.subscribe("OrderCreated", callback)

    bus.publish(Event(event_name="OrderCreated"))

    assert result == ["OrderCreated"]


def test_multiple_handlers():

    bus = EventBus()

    counter = 0

    def a(event):
        nonlocal counter
        counter += 1

    def b(event):
        nonlocal counter
        counter += 1

    bus.subscribe("Signal", a)
    bus.subscribe("Signal", b)

    bus.publish(Event(event_name="Signal"))

    assert counter == 2


def test_unsubscribe():

    bus = EventBus()

    counter = 0

    def callback(event):
        nonlocal counter
        counter += 1

    bus.subscribe("Risk", callback)

    bus.unsubscribe("Risk", callback)

    bus.publish(Event(event_name="Risk"))

    assert counter == 0


def test_unknown_event():

    bus = EventBus()

    bus.publish(Event(event_name="Nothing"))

    assert True