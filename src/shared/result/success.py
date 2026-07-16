from typing import TypeVar

from .result import Result

T = TypeVar("T")


def Success(value: T) -> Result[T]:
    return Result(value=value)