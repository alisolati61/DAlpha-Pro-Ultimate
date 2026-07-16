from dataclasses import dataclass
from typing import Optional


@dataclass
class LiquidityZone:
    buy_side: bool
    sell_side: bool
    price: Optional[float]
    valid: bool


class LiquidityEngine:

    def detect(
        self,
        equal_high: bool,
        equal_low: bool,
        high_price: float,
        low_price: float,
    ) -> LiquidityZone:

        if equal_high:
            return LiquidityZone(
                buy_side=True,
                sell_side=False,
                price=high_price,
                valid=True,
            )

        if equal_low:
            return LiquidityZone(
                buy_side=False,
                sell_side=True,
                price=low_price,
                valid=True,
            )

        return LiquidityZone(
            buy_side=False,
            sell_side=False,
            price=None,
            valid=False,
        )