from __future__ import annotations

import uuid

from src.domain.order import Order
from src.interfaces.exchange_interface import ExchangeInterface


class PaperDriver(ExchangeInterface):

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def health_check(self) -> bool:
        return True

    def get_balance(self):
        return {
            "USDT": 100000,
        }

    def get_positions(self):
        return []

    def place_order(
        self,
        order: Order,
    ) -> str:

        return str(uuid.uuid4())

    def cancel_order(
        self,
        order_id: str,
    ) -> bool:

        return True

    def get_order_status(
        self,
        order_id: str,
    ):

        return "FILLED"

    def get_orderbook(
        self,
        symbol: str,
    ):

        return {}

    def get_ticker(
        self,
        symbol: str,
    ):

        return {
            "symbol": symbol,
            "price": 100000,
        }

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ):

        return []