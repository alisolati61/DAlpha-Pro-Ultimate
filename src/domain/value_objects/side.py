from __future__ import annotations

from enum import Enum


class Side(str, Enum):
    """
    Trading order side.
    """

    BUY = "BUY"
    SELL = "SELL"

    @property
    def is_buy(self) -> bool:
        return self is Side.BUY

    @property
    def is_sell(self) -> bool:
        return self is Side.SELL