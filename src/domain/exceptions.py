"""
Domain Exceptions

تمام Exceptionهای دامنه (Domain) باید از DomainError ارث‌بری کنند.
Infrastructure و Application نباید Exception اختصاصی Domain ایجاد کنند.
"""

from __future__ import annotations


class DomainError(Exception):
    """
    Base class for all domain-related exceptions.
    """

    pass


class ValidationError(DomainError):
    """
    Raised when domain validation fails.
    """

    pass


class BusinessRuleViolation(DomainError):
    """
    Raised when a business rule is violated.
    """

    pass


class EntityNotFoundError(DomainError):
    """
    Raised when an entity cannot be found.
    """

    pass


class DuplicateEntityError(DomainError):
    """
    Raised when attempting to create a duplicate entity.
    """

    pass


class InvalidValueObjectError(ValidationError):
    """
    Raised when a Value Object contains invalid data.
    """

    pass


class InvalidSymbolError(InvalidValueObjectError):
    """
    Raised when a trading symbol is invalid.
    """

    pass