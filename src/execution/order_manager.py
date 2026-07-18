from __future__ import annotations

import math

from src.domain.order import Order


class OrderManager:
    """
    Creates validated domain orders for the execution layer.
    """

    @staticmethod
    def _validate_symbol(
        symbol: str,
    ) -> str:

        if not isinstance(
            symbol,
            str,
        ):

            raise TypeError(
                "symbol must be a string."
            )

        symbol = symbol.strip()

        if not symbol:

            raise ValueError(
                "symbol cannot be empty."
            )

        return symbol

    @staticmethod
    def _validate_side(
        side: str,
    ) -> str:

        if not isinstance(
            side,
            str,
        ):

            raise TypeError(
                "side must be a string."
            )

        side = side.strip().lower()

        if side not in {
            "buy",
            "sell",
        }:

            raise ValueError(
                "side must be 'buy' or 'sell'."
            )

        return side

    @staticmethod
    def _validate_quantity(
        quantity: float,
    ) -> float:

        if isinstance(
            quantity,
            bool,
        ):

            raise TypeError(
                "quantity must be a number."
            )

        if not isinstance(
            quantity,
            (int, float),
        ):

            raise TypeError(
                "quantity must be a number."
            )

        quantity = float(quantity)

        if not math.isfinite(
            quantity
        ):

            raise ValueError(
                "quantity must be finite."
            )

        if quantity <= 0:

            raise ValueError(
                "quantity must be greater than zero."
            )

        return quantity

    @staticmethod
    def _validate_price(
        price: float,
    ) -> float:

        if isinstance(
            price,
            bool,
        ):

            raise TypeError(
                "price must be a number."
            )

        if not isinstance(
            price,
            (int, float),
        ):

            raise TypeError(
                "price must be a number."
            )

        price = float(price)

        if not math.isfinite(
            price
        ):

            raise ValueError(
                "price must be finite."
            )

        if price <= 0:

            raise ValueError(
                "price must be greater than zero."
            )

        return price

    def create_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
    ) -> Order:

        return Order(
            symbol=self._validate_symbol(
                symbol
            ),
            side=self._validate_side(
                side
            ),
            order_type="market",
            quantity=self._validate_quantity(
                quantity
            ),
            price=None,
        )

    def create_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ) -> Order:

        return Order(
            symbol=self._validate_symbol(
                symbol
            ),
            side=self._validate_side(
                side
            ),
            order_type="limit",
            quantity=self._validate_quantity(
                quantity
            ),
            price=self._validate_price(
                price
            ),
        )