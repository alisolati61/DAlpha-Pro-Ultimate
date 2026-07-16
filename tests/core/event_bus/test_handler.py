from src.core.event_bus.event import Event
from src.core.event_bus.handler import EventHandler


def test_handler_executes_callback():

    called = False

    def callback(event: Event):
        nonlocal called
        called = True

    handler = EventHandler(callback)

    handler.handle(Event())

    assert called


def test_handler_returns_value():

    def callback(event: Event):
        return 100

    handler = EventHandler(callback)

    assert handler.handle(Event()) == 100