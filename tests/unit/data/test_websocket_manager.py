import pytest

from src.data.websocket_manager import (
    WebSocketManager,
)


@pytest.mark.asyncio
async def test_start():

    manager = WebSocketManager()

    await manager.start()

    assert manager.running


@pytest.mark.asyncio
async def test_stop():

    manager = WebSocketManager()

    await manager.start()

    await manager.stop()

    assert not manager.running


@pytest.mark.asyncio
async def test_publish():

    manager = WebSocketManager()

    received = []

    async def callback(message):

        received.append(message)

    manager.subscribe(callback)

    await manager.publish(
        {
            "price": 100,
        }
    )

    assert len(received) == 1