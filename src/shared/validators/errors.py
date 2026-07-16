from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValidationError:

    field: str

    message: str