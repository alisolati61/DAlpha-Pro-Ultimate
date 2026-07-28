"""Import-safe compatibility surface for the local Market Data service."""

from __future__ import annotations

from src.data.market_data_feed import MarketDataFeed
from src.data.service import MarketDataService


def create_market_data_service() -> MarketDataService:
    """Create an uninitialized local service without external side effects."""

    return MarketDataService()


__all__ = (
    "MarketDataFeed",
    "MarketDataService",
    "create_market_data_service",
)
