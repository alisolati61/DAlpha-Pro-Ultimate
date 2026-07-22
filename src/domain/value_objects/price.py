from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from .exceptions import InvalidValueObjectError


_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3,10}$")


@dataclass(frozen=True, slots=True)
class Price:
    """
    Immutable asset price.

    Examples:
        Price(Decimal("65000.50"), "USD")
        Price(Decimal("1.0875"), "EUR")
        Price(Decimal("105000"), "USDT")
    """

    value: Decimal
    quote_currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal):
            raise InvalidValueObjectError(
                "Price must be a Decimal instance."
            )

        if self.value <= Decimal("0"):
            raise InvalidValueObjectError(
                "Price must be greater than zero."
            )

        if not isinstance(self.quote_currency, str):
            raise InvalidValueObjectError(
                "Quote currency must be a string."
            )

        currency = self.quote_currency.strip().upper()

        if not _CURRENCY_PATTERN.fullmatch(currency):
            raise InvalidValueObjectError(
                f"Invalid quote currency: {self.quote_currency}"
            )

        object.__setattr__(
            self,
            "quote_currency",
            currency,
        )

    def __str__(self) -> str:
        return f"{self.value} {self.quote_currency}"