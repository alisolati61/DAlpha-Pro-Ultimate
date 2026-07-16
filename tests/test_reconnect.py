import asyncio

from src.exchange.reconnect import ReconnectManager


async def fake_connection():
    raise Exception("Connection Lost")


async def main():

    manager = ReconnectManager()

    try:
        await manager.retry(fake_connection)

    except Exception as e:
        print(e)


asyncio.run(main())