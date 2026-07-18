from __future__ import annotations

from dataclasses import dataclass

from src.data.market_data import MarketData


@dataclass(slots=True)
class ValidationResult:

    valid: bool

    reason: str


class MarketDataValidator:
    """
    Final validation layer before market data
    enters the rest of the system.

    Future
    -------
    - Circuit Breaker
    - Price Spike Detection
    - Exchange Drift Detection
    - Timestamp Validation
    """

    def validate(
        self,
        data: MarketData,
    ) -> ValidationResult:

        if data.price <= 0:

            return ValidationResult(
                False,
                "Invalid price",
            )

        if data.bid <= 0:

            return ValidationResult(
                False,
                "Invalid bid",
            )

        if data.ask <= 0:

            return ValidationResult(
                False,
                "Invalid ask",
            )

        if data.bid > data.ask:

            return ValidationResult(
                False,
                "Bid greater than Ask",
            )

        if data.volume < 0:

            return ValidationResult(
                False,
                "Negative volume",
            )

        return ValidationResult(
            True,
            "OK",
        )