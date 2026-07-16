from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from .result import ValidationResult

T = TypeVar("T")


class Validator(ABC, Generic[T]):

    @abstractmethod
    def validate(self, value: T) -> ValidationResult:
        ...