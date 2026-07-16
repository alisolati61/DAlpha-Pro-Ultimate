from abc import ABC, abstractmethod


class BaseExchange(ABC):

    @abstractmethod
    async def connect(self):
        pass

    @abstractmethod
    async def disconnect(self):
        pass

    @abstractmethod
    async def fetch_ticker(self, symbol: str):
        pass

    @abstractmethod
    async def create_order(self, *args, **kwargs):
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str):
        pass