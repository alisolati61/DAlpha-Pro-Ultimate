"""Validated, thread-safe in-memory order book snapshots."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from threading import RLock
from typing import Any, TypeAlias

from src.data.errors import InvalidOrderBookError

PriceLevel: TypeAlias = tuple[float, float]
_StoredBook: TypeAlias = tuple[
    str,
    tuple[PriceLevel, ...],
    tuple[PriceLevel, ...],
]


def _symbol(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidOrderBookError
    return value.strip()


def _levels(
    value: object,
    *,
    reverse: bool,
) -> tuple[PriceLevel, ...]:
    if (
        isinstance(value, (str, bytes, bytearray))
        or not isinstance(value, Sequence)
    ):
        raise InvalidOrderBookError

    normalized: list[PriceLevel] = []
    prices: set[float] = set()
    for level in value:
        if (
            isinstance(level, (str, bytes, bytearray))
            or not isinstance(level, Sequence)
            or len(level) != 2
        ):
            raise InvalidOrderBookError
        price = _number(level[0], strictly_positive=True)
        quantity = _number(level[1], strictly_positive=False)
        if price in prices:
            raise InvalidOrderBookError
        prices.add(price)
        normalized.append((price, quantity))

    normalized.sort(key=lambda item: item[0], reverse=reverse)
    return tuple(normalized)


def _number(value: Any, *, strictly_positive: bool) -> float:
    if isinstance(value, bool):
        raise InvalidOrderBookError
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise InvalidOrderBookError from error
    if not math.isfinite(normalized):
        raise InvalidOrderBookError
    if strictly_positive and normalized <= 0:
        raise InvalidOrderBookError
    if not strictly_positive and normalized < 0:
        raise InvalidOrderBookError
    return normalized


@dataclass(slots=True)
class OrderBook:
    """Compatibility view with defensively copied list-based levels."""

    symbol: str
    bids: list[PriceLevel]
    asks: list[PriceLevel]


class OrderBookManager:
    """Atomically store the latest normalized book for each symbol.

    Empty bids, empty asks, and fully empty books are accepted. A crossed-book
    check is applied only when both sides contain at least one level.
    """

    def __init__(self) -> None:
        self._books: dict[str, _StoredBook] = {}
        self._lock = RLock()

    def prepare(
        self,
        symbol: str,
        bids: Sequence[Sequence[Any]],
        asks: Sequence[Sequence[Any]],
    ) -> _StoredBook:
        """Validate and normalize without changing manager state."""

        try:
            normalized_symbol = _symbol(symbol)
            normalized_bids = _levels(bids, reverse=True)
            normalized_asks = _levels(asks, reverse=False)
        except InvalidOrderBookError:
            raise
        except Exception as error:
            raise InvalidOrderBookError from error
        if (
            normalized_bids
            and normalized_asks
            and normalized_bids[0][0] > normalized_asks[0][0]
        ):
            raise InvalidOrderBookError
        return (
            normalized_symbol,
            normalized_bids,
            normalized_asks,
        )

    def update(
        self,
        symbol: str,
        bids: Sequence[Sequence[Any]],
        asks: Sequence[Sequence[Any]],
    ) -> OrderBook:
        prepared = self.prepare(symbol, bids, asks)
        with self._lock:
            self._books[prepared[0]] = prepared
        return self._public(prepared)

    def get(self, symbol: str) -> OrderBook | None:
        normalized_symbol = _symbol(symbol)
        with self._lock:
            stored = self._books.get(normalized_symbol)
            return None if stored is None else self._public(stored)

    def best_bid(self, symbol: str) -> PriceLevel | None:
        book = self.get(symbol)
        return None if book is None or not book.bids else book.bids[0]

    def best_ask(self, symbol: str) -> PriceLevel | None:
        book = self.get(symbol)
        return None if book is None or not book.asks else book.asks[0]

    def clear(self) -> None:
        with self._lock:
            self._books.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._books)

    @staticmethod
    def _public(stored: _StoredBook) -> OrderBook:
        return OrderBook(
            symbol=stored[0],
            bids=list(stored[1]),
            asks=list(stored[2]),
        )

    def _snapshot_state(self) -> dict[str, _StoredBook]:
        with self._lock:
            return dict(self._books)

    def _restore_state(
        self,
        state: dict[str, _StoredBook],
    ) -> None:
        with self._lock:
            self._books = dict(state)


__all__ = (
    "OrderBook",
    "OrderBookManager",
    "PriceLevel",
)
