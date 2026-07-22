from __future__ import annotations

import re
from dataclasses import dataclass

from .exceptions import InvalidSymbolError


_SYMBOL_PATTERN = re.compile(
    r"^[A-Z0-9_-]{3,20}$"
)


@dataclass(frozen=True, slots=True)
class Symbol:
    """
    Immutable trading symbol.

    Supported examples:

        BTCUSDT
        ETHUSDT
        EURUSD
        BTC-USD
        XAUUSD

    Slash-separated symbols such as:

        BTC/USDT

    are intentionally rejected because the canonical
    domain representation uses compact or hyphen-separated
    symbols.
    """

    value: str

    def __post_init__(self) -> None:

        if not isinstance(
            self.value,
            str,
        ):

            raise TypeError(
                "Symbol must be a string."
            )

        normalized = self.value.strip().upper()

        if not normalized:

            raise InvalidSymbolError(
                "Symbol cannot be empty."
            )

        if not _SYMBOL_PATTERN.fullmatch(
            normalized
        ):

            raise InvalidSymbolError(
                f"Invalid trading symbol: {self.value}"
            )

        object.__setattr__(
            self,
            "value",
            normalized,
        )

    def __str__(self) -> str:

        return self.value