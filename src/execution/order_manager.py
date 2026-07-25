"""Validated domain-order construction for the execution layer.

The manager creates independent ``Order`` objects while preserving the public
string contract used by the existing domain model:

- side: ``"buy"`` or ``"sell"``;
- order type: ``"market"`` or ``"limit"``;
- quantity and limit price: normalized ``float`` values.

Exchange-specific quantity steps, price ticks, minimum notionals, and precision
rounding belong to the exchange adapter or order-normalization layer.
"""

from __future__ import annotations

from math import isfinite
from numbers import Real

from src.domain.order import Order

_MAX_SYMBOL_LENGTH = 100
_VALID_SIDES = frozenset(
    {
        "buy",
        "sell",
    }
)
_VALID_ORDER_TYPES = frozenset(
    {
        "market",
        "limit",
    }
)


class OrderManager:
    """Create validated domain orders for execution."""

    @staticmethod
    def _validate_symbol(
        symbol: str,
    ) -> str:
        if not isinstance(symbol, str):
            raise TypeError(
                "symbol must be a string."
            )

        normalized = symbol.strip()

        if not normalized:
            raise ValueError(
                "symbol cannot be empty."
            )

        if len(normalized) > _MAX_SYMBOL_LENGTH:
            raise ValueError(
                "symbol must not exceed "
                f"{_MAX_SYMBOL_LENGTH} characters."
            )

        return normalized

    @staticmethod
    def _validate_side(
        side: str,
    ) -> str:
        if not isinstance(side, str):
            raise TypeError(
                "side must be a string."
            )

        normalized = side.strip().lower()

        if normalized not in _VALID_SIDES:
            raise ValueError(
                "side must be 'buy' or 'sell'."
            )

        return normalized

    @staticmethod
    def _validate_order_type(
        order_type: str,
    ) -> str:
        if not isinstance(order_type, str):
            raise TypeError(
                "order_type must be a string."
            )

        normalized = order_type.strip().lower()

        if normalized not in _VALID_ORDER_TYPES:
            raise ValueError(
                "order_type must be 'market' "
                "or 'limit'."
            )

        return normalized

    @staticmethod
    def _validate_quantity(
        quantity: float,
    ) -> float:
        return _validate_positive_finite_number(
            quantity,
            "quantity",
        )

    @staticmethod
    def _validate_price(
        price: float,
    ) -> float:
        return _validate_positive_finite_number(
            price,
            "price",
        )

    def create_order(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
    ) -> Order:
        """Create a validated market or limit order.

        Market orders must not carry a limit price. Limit orders require one.
        """

        normalized_symbol = self._validate_symbol(
            symbol
        )
        normalized_side = self._validate_side(
            side
        )
        normalized_order_type = (
            self._validate_order_type(
                order_type
            )
        )
        normalized_quantity = (
            self._validate_quantity(
                quantity
            )
        )

        if normalized_order_type == "market":
            if price is not None:
                raise ValueError(
                    "market order price must be None."
                )

            normalized_price = None
        else:
            if price is None:
                raise ValueError(
                    "limit order price is required."
                )

            normalized_price = self._validate_price(
                price
            )

        return Order(
            symbol=normalized_symbol,
            side=normalized_side,
            order_type=normalized_order_type,
            quantity=normalized_quantity,
            price=normalized_price,
        )

    def create_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
    ) -> Order:
        """Create a validated market order."""

        return self.create_order(
            symbol=symbol,
            side=side,
            order_type="market",
            quantity=quantity,
            price=None,
        )

    def create_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ) -> Order:
        """Create a validated limit order.

        This path validates ``price`` directly so the historical API keeps
        raising ``TypeError`` for non-numeric values such as ``None``.
        """

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


def _validate_positive_finite_number(
    value: object,
    field_name: str,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
    ):
        raise TypeError(
            f"{field_name} must be a number."
        )

    normalized = float(value)

    if not isfinite(normalized):
        raise ValueError(
            f"{field_name} must be finite."
        )

    if normalized <= 0.0:
        raise ValueError(
            f"{field_name} must be greater than zero."
        )

    return normalized


__all__ = (
    "OrderManager",
)