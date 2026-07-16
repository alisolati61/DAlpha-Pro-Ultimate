from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class OrderBook:

    symbol: str

    bids: list[tuple[float, float]] = field(default_factory=list)

    asks: list[tuple[float, float]] = field(default_factory=list)


class OrderBookManager:

    def __init__(self):

        self._books: dict[str, OrderBook] = {}

    def update(

        self,

        symbol: str,

        bids: list[tuple[float, float]],

        asks: list[tuple[float, float]],

    ) -> None:

        self._books[symbol] = OrderBook(

            symbol=symbol,

            bids=bids,

            asks=asks,

        )

    def get(

        self,

        symbol: str,

    ) -> OrderBook | None:

        return self._books.get(symbol)

    def exists(

        self,

        symbol: str,

    ) -> bool:

        return symbol in self._books

    def best_bid(

        self,

        symbol: str,

    ) -> float | None:

        book = self.get(symbol)

        if not book or not book.bids:
            return None

        return book.bids[0][0]

    def best_ask(

        self,

        symbol: str,

    ) -> float | None:

        book = self.get(symbol)

        if not book or not book.asks:
            return None

        return book.asks[0][0]