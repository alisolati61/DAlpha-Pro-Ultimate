from typing import Optional

from src.domain.order import Order


class OrderManager:

    def create_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
    ) -> Order:

        return Order(
            symbol=symbol,
            side=side,
            order_type="market",
            quantity=quantity,
        )

    def create_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ) -> Order:

        return Order(
            symbol=symbol,
            side=side,
            order_type="limit",
            quantity=quantity,
            price=price,
        )