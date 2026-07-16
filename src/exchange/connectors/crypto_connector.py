from src.exchange.ccxt_exchange import CCXTExchange


class CryptoConnector:

    def __init__(self, exchange_name: str = "bingx"):
        self.exchange = CCXTExchange(exchange_name)

    async def connect(self):
        await self.exchange.connect()

    async def disconnect(self):
        await self.exchange.disconnect()

    async def get_ticker(self, symbol: str):
        return await self.exchange.fetch_ticker(symbol)

    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price=None,
    ):
        return await self.exchange.create_order(
            symbol,
            order_type,
            side,
            amount,
            price,
        )

    async def cancel_order(self, order_id: str):
        return await self.exchange.cancel_order(order_id)