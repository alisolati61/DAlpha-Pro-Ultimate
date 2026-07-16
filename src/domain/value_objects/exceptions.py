from __future__ import annotations


class ValueObjectError(ValueError):
    """
    Base exception for Value Objects.
    """


class InvalidValueObjectError(ValueObjectError):
    """
    Raised when a Value Object contains invalid data.
    """


class InvalidSymbolError(InvalidValueObjectError):
    """
    Raised when a trading symbol is invalid.
    """