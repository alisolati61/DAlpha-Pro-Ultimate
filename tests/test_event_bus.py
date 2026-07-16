from src.core.event_bus.event import Event
from src.core.event_bus.types import Handler
from src.core.event_bus.subscription import SubscriptionManager
from src.core.event_bus.exceptions import (
    DuplicateSubscriptionError,
    EventBusError,
    EventDispatchError,
    HandlerNotFoundError,
    SubscriptionError,
)


# ----------------------------------------------------------------------
# Event
# ----------------------------------------------------------------------

def test_event_creation():
    event = Event()

    assert event.source == "system"
    assert event.payload == {}
    assert event.event_name == "Event"


def test_event_payload():
    event = Event(
        source="CoinEx",
        payload={
            "symbol": "BTCUSDT",
            "price": 100000,
        },
    )

    assert event.payload["symbol"] == "BTCUSDT"


def test_event_id_exists():
    event = Event()

    assert event.event_id is not None


def test_timestamp_exists():
    event = Event()

    assert event.timestamp is not None


# ----------------------------------------------------------------------
# Handler
# ----------------------------------------------------------------------

def test_handler_type():

    def callback(event: Event):
        return None

    handler: Handler = callback

    assert callable(handler)


# ----------------------------------------------------------------------
# Exceptions
# ----------------------------------------------------------------------

def test_base_exception():
    assert isinstance(EventBusError(), Exception)


def test_subscription_exception():
    assert isinstance(
        SubscriptionError(),
        EventBusError,
    )


def test_dispatch_exception():
    assert isinstance(
        EventDispatchError(),
        EventBusError,
    )


def test_duplicate_subscription():
    assert isinstance(
        DuplicateSubscriptionError(),
        SubscriptionError,
    )


def test_handler_not_found():
    assert isinstance(
        HandlerNotFoundError(),
        SubscriptionError,
    )


# ----------------------------------------------------------------------
# SubscriptionManager
# ----------------------------------------------------------------------

def test_subscribe():

    manager = SubscriptionManager()

    def handler(event: Event):
        pass

    manager.subscribe(Event, handler)

    assert manager.count() == 1


def test_duplicate_subscribe():

    manager = SubscriptionManager()

    def handler(event: Event):
        pass

    manager.subscribe(Event, handler)

    try:
        manager.subscribe(Event, handler)
        assert False
    except DuplicateSubscriptionError:
        assert True


def test_unsubscribe():

    manager = SubscriptionManager()

    def handler(event: Event):
        pass

    manager.subscribe(Event, handler)

    manager.unsubscribe(Event, handler)

    assert manager.count() == 0


def test_handlers_for():

    manager = SubscriptionManager()

    def handler(event: Event):
        pass

    manager.subscribe(Event, handler)

    handlers = manager.handlers_for(Event)

    assert len(handlers) == 1


def test_clear():

    manager = SubscriptionManager()

    def handler(event: Event):
        pass

    manager.subscribe(Event, handler)

    manager.clear()

    assert manager.count() == 0