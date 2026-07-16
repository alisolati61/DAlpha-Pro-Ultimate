from __future__ import annotations

from enum import Enum


class OrderStatus(str, Enum):
    """
    Trading order status.
    """

    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

    @property
    def is_open(self) -> bool:
        return self in {
            OrderStatus.NEW,
            OrderStatus.PARTIALLY_FILLED,
        }

    @property
    def is_closed(self) -> bool:
        return self in {
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        }

    @property
    def is_filled(self) -> bool:
        return self is OrderStatus.FILLED