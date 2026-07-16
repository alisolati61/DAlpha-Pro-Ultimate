from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Symbol:

    value: str