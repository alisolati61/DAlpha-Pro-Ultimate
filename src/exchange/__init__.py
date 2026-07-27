"""Stable public API for the exchange subsystem.

The package uses lazy attribute loading so importing ``src.exchange`` does not
eagerly import optional exchange drivers or initialize transport dependencies.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any, Final

_EXPORTS: Final[dict[str, tuple[str, str]]] = {
    # Core contract and orchestration.
    "BaseExchange": (".base", "BaseExchange"),
    "ExchangeManager": (".manager", "ExchangeManager"),
    "ExchangeFactory": (
        ".exchange_factory",
        "ExchangeFactory",
    ),
    "ExchangeType": (".exchange_factory", "ExchangeType"),
    # Concrete adapters and facades.
    "BingXAdapter": (".bingx_adapter", "BingXAdapter"),
    "BingXHttpClient": (
        ".bingx_client",
        "BingXHttpClient",
    ),
    "CCXTExchange": (".ccxt_exchange", "CCXTExchange"),
    "CryptoConnector": (
        ".connectors.crypto_connector",
        "CryptoConnector",
    ),
    # Resilience and transport utilities.
    "RateLimiter": (".ratelimiter", "RateLimiter"),
    "ReconnectManager": (
        ".reconnect",
        "ReconnectManager",
    ),
    "WebSocketManager": (
        ".websocket",
        "WebSocketManager",
    ),
    "WebSocketState": (
        ".websocket",
        "WebSocketState",
    ),
    "ExchangeWebSocket": (
        ".websocket",
        "ExchangeWebSocket",
    ),
    # Typed exchange failures.
    "ExchangeError": (".exceptions", "ExchangeError"),
    "AuthenticationError": (
        ".exceptions",
        "AuthenticationError",
    ),
    "RateLimitError": (".exceptions", "RateLimitError"),
    "InsufficientFundsError": (
        ".exceptions",
        "InsufficientFundsError",
    ),
    "InvalidSymbolError": (
        ".exceptions",
        "InvalidSymbolError",
    ),
    "OrderError": (".exceptions", "OrderError"),
    "NetworkError": (".exceptions", "NetworkError"),
    "WebSocketError": (".exceptions", "WebSocketError"),
    "ExchangeNotAvailableError": (
        ".exceptions",
        "ExchangeNotAvailableError",
    ),
    # Validated BingX boundary models.
    "BingXBalance": (".models", "BingXBalance"),
    "BingXPosition": (".models", "BingXPosition"),
    "BingXOrder": (".models", "BingXOrder"),
    "BingXTicker": (".models", "BingXTicker"),
    "BingXOrderBook": (".models", "BingXOrderBook"),
    "BingXKline": (".models", "BingXKline"),
    "BingXFundingRate": (
        ".models",
        "BingXFundingRate",
    ),
    "BingXTrade": (".models", "BingXTrade"),
    "BingXOrderSide": (".models", "BingXOrderSide"),
    "BingXPositionSide": (
        ".models",
        "BingXPositionSide",
    ),
    "BingXOrderType": (".models", "BingXOrderType"),
    "BingXTimeInForce": (
        ".models",
        "BingXTimeInForce",
    ),
    "BingXOrderStatus": (
        ".models",
        "BingXOrderStatus",
    ),
}

__all__ = tuple(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Resolve one declared public symbol on first access."""

    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc

    module = import_module(module_name, __name__)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return a deterministic interactive namespace."""

    return sorted(set(globals()).union(__all__))


if TYPE_CHECKING:
    from .base import BaseExchange
    from .bingx_adapter import BingXAdapter
    from .bingx_client import BingXHttpClient
    from .ccxt_exchange import CCXTExchange
    from .connectors.crypto_connector import CryptoConnector
    from .exceptions import (
        AuthenticationError,
        ExchangeError,
        ExchangeNotAvailableError,
        InsufficientFundsError,
        InvalidSymbolError,
        NetworkError,
        OrderError,
        RateLimitError,
        WebSocketError,
    )
    from .exchange_factory import ExchangeFactory, ExchangeType
    from .manager import ExchangeManager
    from .models import (
        BingXBalance,
        BingXFundingRate,
        BingXKline,
        BingXOrder,
        BingXOrderBook,
        BingXOrderSide,
        BingXOrderStatus,
        BingXOrderType,
        BingXPosition,
        BingXPositionSide,
        BingXTicker,
        BingXTimeInForce,
        BingXTrade,
    )
    from .ratelimiter import RateLimiter
    from .reconnect import ReconnectManager
    from .websocket import (
        ExchangeWebSocket,
        WebSocketManager,
        WebSocketState,
    )