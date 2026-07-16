import ccxt.async_support as ccxt

from .base import BaseExchange


class CCXTExchange(BaseExchange):

    def __init__(self, exchange_name: str):
        exchange_class = getattr(ccxt, exchange_name)
        self.exchange = exchange_class()

    async def connect(self):
        await self.exchange.load_markets()

    async def disconnect(self):
        await self.exchange.close()

    async def fetch_ticker(self, symbol: str):
        return await self.exchange.fetch_ticker(symbol)

    async def create_order(self, *args, **kwargs):
        return await self.exchange.create_order(*args, **kwargs)

    async def cancel_order(self, order_id: str):
        return await self.exchange.cancel_order(order_id)