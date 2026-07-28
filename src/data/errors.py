"""Sanitized failures for the canonical local Data service."""

from __future__ import annotations


class DataServiceError(Exception):
    """Base failure with stable, non-sensitive public text."""

    public_message = "Local market data operation failed."

    def __init__(self) -> None:
        super().__init__(self.public_message)


class DataServiceUnavailableError(DataServiceError):
    """Ingestion was attempted while the service was not accepting data."""

    public_message = "Local market data service is not running."


class InvalidDataPacketError(DataServiceError):
    """A raw candle packet failed its local validation contract."""

    public_message = "Market data packet is invalid."


class InvalidOrderBookError(DataServiceError):
    """An order book snapshot failed local validation."""

    public_message = "Order book snapshot is invalid."


class IngestionTransactionError(DataServiceError):
    """A prepared ingestion transaction could not be committed."""

    public_message = "Market data ingestion transaction failed."


__all__ = (
    "DataServiceError",
    "DataServiceUnavailableError",
    "IngestionTransactionError",
    "InvalidDataPacketError",
    "InvalidOrderBookError",
)
