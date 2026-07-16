from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .exceptions import InvalidValueObjectError


@dataclass(frozen=True, slots=True)
class Quantity:
    """
    Immutable trading quantity.

    Examples:
        Quantity(Decimal("0.001"))
        Quantity(Decimal("10"))
    """

    value: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal):
            raise InvalidValueObjectError(
                "Quantity must be a Decimal instance."
            )

        if self.value <= Decimal("0"):
            raise InvalidValueObjectError(
                "Quantity must be greater than zero."
            )

    def __add__(self, other: "Quantity") -> "Quantity":
        return Quantity(self.value + other.value)

    def __sub__(self, other: "Quantity") -> "Quantity":
        result = self.value - other.value

        if result <= Decimal("0"):
            raise InvalidValueObjectError(
                "Quantity cannot become zero or negative."
            )

        return Quantity(result)

    def __mul__(self, multiplier: Decimal) -> "Quantity":
        if not isinstance(multiplier, Decimal):
            raise InvalidValueObjectError(
                "Multiplier must be a Decimal instance."
            )

        return Quantity(self.value * multiplier)

    def __str__(self) -> str:
        return str(self.value)