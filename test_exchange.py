import asyncio

from src.exchange import CCXTExchange


async def main():
    exchange = CCXTExchange("bingx")

    await exchange.connect()

    ticker = await exchange.fetch_ticker("BTC/USDT")

    print(ticker["last"])

    await exchange.disconnect()


if __name__ == "__main__":
    asyncio.run(main())