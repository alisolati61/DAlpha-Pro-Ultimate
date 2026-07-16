import asyncio

from src.exchange.websocket import WebSocketManager


async def main():

    ws = WebSocketManager()

    await ws.connect()

    await ws.disconnect()

    await ws.reconnect()


asyncio.run(main())