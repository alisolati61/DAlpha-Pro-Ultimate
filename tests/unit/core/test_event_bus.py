from src.core.event_bus.event import Event
from src.core.event_bus.event_bus import EventBus


def test_subscribe():

    bus = EventBus()

    def callback(event):
        pass

    bus.subscribe(
        "tick",
        callback,
    )

    assert bus.listener_count("tick") == 1


def test_publish():

    bus = EventBus()

    received = []

    def callback(event):

        received.append(event.payload)

    bus.subscribe(
        "tick",
        callback,
    )

    bus.publish(
        Event(
            event_name="tick",
            payload=100,
        )
    )

    assert received == [100]


def test_unsubscribe():

    bus = EventBus()

    def callback(event):
        pass

    bus.subscribe(
        "tick",
        callback,
    )

    bus.unsubscribe(
        "tick",
        callback,
    )

    assert bus.listener_count("tick") == 0


def test_clear():

    bus = EventBus()

    def callback(event):
        pass

    bus.subscribe(
        "tick",
        callback,
    )

    bus.clear()

    assert bus.listener_count("tick") == 0