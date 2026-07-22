# src/exchange/exceptions.py (فایل جدید)
"""
BingX-specific and general exchange exceptions.
Designed to be extensible for other exchanges.
"""

from src.core.exceptions.base import AlphaError


class ExchangeError(AlphaError):
    """Base exception for all exchange-related errors."""
    
    def __init__(
        self,
        message: str,
        exchange: str = "unknown",
        error_code: str | None = None,
        raw_response: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.exchange = exchange
        self.error_code = error_code
        self.raw_response = raw_response or {}


class AuthenticationError(ExchangeError):
    """API key invalid, expired, or insufficient permissions."""
    pass


class RateLimitError(ExchangeError):
    """Rate limit exceeded."""
    
    def __init__(
        self,
        message: str,
        exchange: str = "unknown",
        retry_after: int = 60,
        **kwargs,
    ) -> None:
        super().__init__(message, exchange, **kwargs)
        self.retry_after = retry_after


class InsufficientFundsError(ExchangeError):
    """Not enough balance for the operation."""
    pass


class InvalidSymbolError(ExchangeError):
    """Trading pair not found or not supported."""
    pass


class OrderError(ExchangeError):
    """Order placement/modification failed."""
    pass


class NetworkError(ExchangeError):
    """Connection or timeout issues."""
    pass


class WebSocketError(ExchangeError):
    """WebSocket-specific errors."""
    pass


class ExchangeNotAvailableError(ExchangeError):
    """Exchange is down or in maintenance."""
    pass