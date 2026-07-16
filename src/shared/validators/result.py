from dataclasses import dataclass, field

from .errors import ValidationError


@dataclass(slots=True)
class ValidationResult:

    errors: list[ValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, field: str, message: str) -> None:
        self.errors.append(
            ValidationError(
                field=field,
                message=message,
            )
        )