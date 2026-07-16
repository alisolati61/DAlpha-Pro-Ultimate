from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re

from .exceptions import InvalidValueObjectError


_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True, slots=True)
class Money:
    """
    Immutable monetary value.

    Examples:
        Money(Decimal("100.50"), "USD")
        Money(Decimal("2500"), "EUR")
    """

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise InvalidValueObjectError(
                "Amount must be a Decimal instance."
            )

        currency = self.currency.strip().upper()

        if not _CURRENCY_PATTERN.fullmatch(currency):
            raise InvalidValueObjectError(
                f"Invalid currency: {self.currency}"
            )

        object.__setattr__(self, "currency", currency)

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise InvalidValueObjectError(
                "Currency mismatch."
            )

        return Money(
            amount=self.amount + other.amount,
            currency=self.currency,
        )

    def __sub__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise InvalidValueObjectError(
                "Currency mismatch."
            )

        return Money(
            amount=self.amount - other.amount,
            currency=self.currency,
        )

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"