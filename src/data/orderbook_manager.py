from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class OrderBook:
    symbol: str
    bids: list[tuple[float, float]]
    asks: list[tuple[float, float]]


class OrderBookManager:
    """
    Stores the latest order book snapshot for each symbol.
    """

    def __init__(self) -> None:

        self._books: dict[str, OrderBook] = {}

    # ------------------------------------------------

    def update(
        self,
        symbol: str,
        bids: list[tuple[float, float]],
        asks: list[tuple[float, float]],
    ) -> None:

        self._books[symbol] = OrderBook(
            symbol=symbol,
            bids=[(float(p), float(q)) for p, q in bids],
            asks=[(float(p), float(q)) for p, q in asks],
        )

    # ------------------------------------------------

    def get(
        self,
        symbol: str,
    ) -> OrderBook | None:

        return self._books.get(symbol)

    # ------------------------------------------------

    def best_bid(
        self,
        symbol: str,
    ) -> tuple[float, float] | None:

        book = self.get(symbol)

        if not book or not book.bids:
            return None

        return max(book.bids, key=lambda x: x[0])

    # ------------------------------------------------

    def best_ask(
        self,
        symbol: str,
    ) -> tuple[float, float] | None:

        book = self.get(symbol)

        if not book or not book.asks:
            return None

        return min(book.asks, key=lambda x: x[0])

    # ------------------------------------------------

    def clear(self) -> None:

        self._books.clear()