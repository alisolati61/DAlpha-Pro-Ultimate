"""
Market Data Feed

دریافت داده از صرافی
فعلاً نسخه Mock
بعداً Binance و Bybit به آن متصل می‌شوند.
"""

import asyncio
import random
from datetime import datetime

from .market_data import MarketData


class MarketDataFeed:

    def __init__(self):
        self.running = False

    async def start(self):

        self.running = True

        while self.running:

            price = random.uniform(65000, 66000)

            data = MarketData(
                symbol="BTCUSDT",
                price=price,
                bid=price - 2,
                ask=price + 2,
                volume=random.uniform(1, 50),
                timestamp=datetime.utcnow()
            )

            await self.on_tick(data)

            await asyncio.sleep(1)

    async def on_tick(self, market_data: MarketData):

        print(
            f"{market_data.symbol} | "
            f"{market_data.price:.2f} | "
            f"Vol={market_data.volume:.2f}"
        )

    def stop(self):
        self.running = False