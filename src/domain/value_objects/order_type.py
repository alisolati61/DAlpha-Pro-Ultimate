from __future__ import annotations

from enum import Enum


class OrderType(str, Enum):
    """
    Trading order type.
    """

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"

    @property
    def is_market(self) -> bool:
        return self is OrderType.MARKET

    @property
    def is_limit(self) -> bool:
        return self in {
            OrderType.LIMIT,
            OrderType.STOP_LIMIT,
            OrderType.TAKE_PROFIT_LIMIT,
        }