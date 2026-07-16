from __future__ import annotations

from datetime import datetime

from src.domain.market_data import MarketData


class MarketDataNormalizer:
    """
    Converts raw exchange data into a unified MarketData object.
    """

    def normalize_binance(self, raw: dict) -> MarketData:

        return MarketData(
            symbol=raw["symbol"],
            price=float(raw["price"]),
            bid=float(raw["bid"]),
            ask=float(raw["ask"]),
            volume=float(raw["volume"]),
            timestamp=datetime.fromtimestamp(raw["timestamp"]),
        )

    def normalize_bybit(self, raw: dict) -> MarketData:

        return MarketData(
            symbol=raw["symbol"],
            price=float(raw["lastPrice"]),
            bid=float(raw["bidPrice"]),
            ask=float(raw["askPrice"]),
            volume=float(raw["volume24h"]),
            timestamp=datetime.fromtimestamp(raw["timestamp"]),
        )