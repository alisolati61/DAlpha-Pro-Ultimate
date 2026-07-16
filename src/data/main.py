import asyncio

from market_data_feed import MarketDataFeed


async def main():

    feed = MarketDataFeed()

    await feed.start()


if __name__ == "__main__":

    asyncio.run(main())