from __future__ import annotations

import re
from dataclasses import dataclass

from .exceptions import InvalidValueObjectError
from .symbol import Symbol


_ASSET_PATTERN = re.compile(r"^[A-Z0-9]{2,10}$")


@dataclass(frozen=True, slots=True)
class Market:
    """
    Immutable market definition.

    Examples:
        BTC / USDT
        EUR / USD
        XAU / USD
    """

    base_asset: str
    quote_asset: str
    symbol: Symbol

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise InvalidValueObjectError(
                "symbol must be a Symbol instance."
            )

        base = self.base_asset.strip().upper()
        quote = self.quote_asset.strip().upper()

        if not _ASSET_PATTERN.fullmatch(base):
            raise InvalidValueObjectError(
                f"Invalid base asset: {self.base_asset}"
            )

        if not _ASSET_PATTERN.fullmatch(quote):
            raise InvalidValueObjectError(
                f"Invalid quote asset: {self.quote_asset}"
            )

        if base == quote:
            raise InvalidValueObjectError(
                "Base and quote assets must be different."
            )

        object.__setattr__(self, "base_asset", base)
        object.__setattr__(self, "quote_asset", quote)

    def __str__(self) -> str:
        return f"{self.base_asset}/{self.quote_asset}"