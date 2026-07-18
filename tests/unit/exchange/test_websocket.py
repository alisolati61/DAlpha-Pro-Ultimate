import pytest

from src.exchange.websocket import ExchangeWebSocket


@pytest.mark.asyncio
async def test_connect():

    ws = ExchangeWebSocket()

    await ws.connect()

    assert ws.connected


@pytest.mark.asyncio
async def test_disconnect():

    ws = ExchangeWebSocket()

    await ws.connect()

    await ws.disconnect()

    assert not ws.connected


@pytest.mark.asyncio
async def test_reconnect():

    ws = ExchangeWebSocket()

    assert await ws.reconnect()


@pytest.mark.asyncio
async def test_listen():

    ws = ExchangeWebSocket()

    await ws.connect()

    called = {"ok": False}

    async def handler(data):

        called["ok"] = True

    await ws.listen(handler)

    assert called["ok"]


@pytest.mark.asyncio
async def test_listen_without_connection():

    ws = ExchangeWebSocket()

    async def handler(data):

        pass

    with pytest.raises(RuntimeError):

        await ws.listen(handler)