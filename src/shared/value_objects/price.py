from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Price:

    value: Decimal

    @classmethod
    def from_float(cls, value: float):

        return cls(Decimal(str(value)))

    def __float__(self):

        return float(self.value)