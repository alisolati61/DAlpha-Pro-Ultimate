from __future__ import annotations

from typing import Generic, TypeVar

from src.shared.result.exceptions import InvalidResultError

T = TypeVar("T")


class Result(Generic[T]):

    def __init__(self, value: T | None = None, error: str | None = None):

        if (value is None) == (error is None):
            raise InvalidResultError(
                "Result must contain either a value or an error."
            )

        self._value = value
        self._error = error

    @property
    def is_success(self) -> bool:
        return self._error is None

    @property
    def is_failure(self) -> bool:
        return self._error is not None

    @property
    def value(self) -> T:
        if self.is_failure:
            raise ValueError("Cannot access value of failed Result.")
        return self._value

    @property
    def error(self) -> str:
        if self.is_success:
            raise ValueError("Successful Result has no error.")
        return self._error