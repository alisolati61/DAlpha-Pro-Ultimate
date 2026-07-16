from dataclasses import dataclass

from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Money:

    value: Decimal

    currency: str = "USDT"