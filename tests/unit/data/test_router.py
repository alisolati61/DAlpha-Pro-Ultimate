from src.data.router import DataRouter


def test_subscribe():

    router = DataRouter()

    def handler(data):
        pass

    router.subscribe(
        "tick",
        handler,
    )

    assert router.subscribers("tick") == 1


def test_publish():

    router = DataRouter()

    received = []

    def handler(data):

        received.append(data)

    router.subscribe(
        "tick",
        handler,
    )

    router.publish(
        "tick",
        123,
    )

    assert received == [123]


def test_unsubscribe():

    router = DataRouter()

    def handler(data):
        pass

    router.subscribe(
        "tick",
        handler,
    )

    router.unsubscribe(
        "tick",
        handler,
    )

    assert router.subscribers("tick") == 0


def test_duplicate():

    router = DataRouter()

    def handler(data):
        pass

    router.subscribe(
        "tick",
        handler,
    )

    router.subscribe(
        "tick",
        handler,
    )

    assert router.subscribers("tick") == 1


def test_clear():

    router = DataRouter()

    def handler(data):
        pass

    router.subscribe(
        "tick",
        handler,
    )

    router.clear()

    assert router.subscribers("tick") == 0


def test_multiple_events():

    router = DataRouter()

    def a(data):
        pass

    def b(data):
        pass

    router.subscribe("tick", a)

    router.subscribe("orderbook", b)

    assert router.subscribers("tick") == 1

    assert router.subscribers("orderbook") == 1