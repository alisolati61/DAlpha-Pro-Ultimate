from __future__ import annotations

from src.domain.market_data import MarketData


class MarketDataValidator:
    """
    Validates normalized market data before it enters the system.
    """

    def validate(
        self,
        data: MarketData,
    ) -> bool:

        if data.symbol == "":
            return False

        if data.price <= 0:
            return False

        if data.bid <= 0:
            return False

        if data.ask <= 0:
            return False

        if data.bid > data.ask:
            return False

        if data.volume < 0:
            return False

        return True