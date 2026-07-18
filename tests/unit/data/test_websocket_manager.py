from src.data.websocket_manager import (
    WebSocketManager,
)


def test_connect():

    ws = WebSocketManager()

    ws.connect(
        "wss://stream.binance.com"
    )

    assert ws.connected


def test_disconnect():

    ws = WebSocketManager()

    ws.connect(
        "abc"
    )

    ws.disconnect()

    assert not ws.connected


def test_endpoint():

    ws = WebSocketManager()

    ws.connect(
        "endpoint"
    )

    assert ws.endpoint == "endpoint"


def test_default():

    ws = WebSocketManager()

    assert ws.connected is False


def test_types():

    ws = WebSocketManager()

    ws.connect(
        "abc"
    )

    assert isinstance(
        ws.connected,
        bool,
    )

    assert isinstance(
        ws.endpoint,
        str,
    )