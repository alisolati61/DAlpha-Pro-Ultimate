from typing import Any

from .market_data import MarketData


class MarketDataNormalizer:
    """
    Normalize market data from different exchanges into
    a unified MarketData model.
    """

    @staticmethod
    def normalize_ticker(
        exchange: str,
        symbol: str,
        ticker: dict[str, Any],
    ) -> MarketData:

        return MarketData(
            symbol=symbol,
            last_price=float(ticker.get("last", 0.0)),
            bid=float(ticker.get("bid", 0.0)),
            ask=float(ticker.get("ask", 0.0)),
            volume=float(ticker.get("baseVolume", 0.0)),
            timestamp=ticker.get("timestamp"),
            exchange=exchange,
        )