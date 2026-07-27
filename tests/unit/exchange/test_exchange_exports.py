"""Contract tests for the public exchange package surface."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import src.exchange as exchange_package

EXPECTED_EXPORTS: dict[str, tuple[str, str]] = {
    "BaseExchange": ("src.exchange.base", "BaseExchange"),
    "ExchangeManager": (
        "src.exchange.manager",
        "ExchangeManager",
    ),
    "ExchangeFactory": (
        "src.exchange.exchange_factory",
        "ExchangeFactory",
    ),
    "ExchangeType": (
        "src.exchange.exchange_factory",
        "ExchangeType",
    ),
    "BingXAdapter": (
        "src.exchange.bingx_adapter",
        "BingXAdapter",
    ),
    "BingXHttpClient": (
        "src.exchange.bingx_client",
        "BingXHttpClient",
    ),
    "CCXTExchange": (
        "src.exchange.ccxt_exchange",
        "CCXTExchange",
    ),
    "CryptoConnector": (
        "src.exchange.connectors.crypto_connector",
        "CryptoConnector",
    ),
    "RateLimiter": (
        "src.exchange.ratelimiter",
        "RateLimiter",
    ),
    "ReconnectManager": (
        "src.exchange.reconnect",
        "ReconnectManager",
    ),
    "WebSocketManager": (
        "src.exchange.websocket",
        "WebSocketManager",
    ),
    "WebSocketState": (
        "src.exchange.websocket",
        "WebSocketState",
    ),
    "ExchangeWebSocket": (
        "src.exchange.websocket",
        "ExchangeWebSocket",
    ),
    "ExchangeError": (
        "src.exchange.exceptions",
        "ExchangeError",
    ),
    "AuthenticationError": (
        "src.exchange.exceptions",
        "AuthenticationError",
    ),
    "RateLimitError": (
        "src.exchange.exceptions",
        "RateLimitError",
    ),
    "InsufficientFundsError": (
        "src.exchange.exceptions",
        "InsufficientFundsError",
    ),
    "InvalidSymbolError": (
        "src.exchange.exceptions",
        "InvalidSymbolError",
    ),
    "OrderError": (
        "src.exchange.exceptions",
        "OrderError",
    ),
    "NetworkError": (
        "src.exchange.exceptions",
        "NetworkError",
    ),
    "WebSocketError": (
        "src.exchange.exceptions",
        "WebSocketError",
    ),
    "ExchangeNotAvailableError": (
        "src.exchange.exceptions",
        "ExchangeNotAvailableError",
    ),
    "BingXBalance": (
        "src.exchange.models",
        "BingXBalance",
    ),
    "BingXPosition": (
        "src.exchange.models",
        "BingXPosition",
    ),
    "BingXOrder": ("src.exchange.models", "BingXOrder"),
    "BingXTicker": (
        "src.exchange.models",
        "BingXTicker",
    ),
    "BingXOrderBook": (
        "src.exchange.models",
        "BingXOrderBook",
    ),
    "BingXKline": ("src.exchange.models", "BingXKline"),
    "BingXFundingRate": (
        "src.exchange.models",
        "BingXFundingRate",
    ),
    "BingXTrade": ("src.exchange.models", "BingXTrade"),
    "BingXOrderSide": (
        "src.exchange.models",
        "BingXOrderSide",
    ),
    "BingXPositionSide": (
        "src.exchange.models",
        "BingXPositionSide",
    ),
    "BingXOrderType": (
        "src.exchange.models",
        "BingXOrderType",
    ),
    "BingXTimeInForce": (
        "src.exchange.models",
        "BingXTimeInForce",
    ),
    "BingXOrderStatus": (
        "src.exchange.models",
        "BingXOrderStatus",
    ),
}


def test_public_export_manifest_is_explicit_and_stable() -> None:
    assert exchange_package.__all__ == tuple(EXPECTED_EXPORTS)
    assert len(exchange_package.__all__) == len(
        set(exchange_package.__all__)
    )


@pytest.mark.parametrize(
    ("public_name", "target"),
    EXPECTED_EXPORTS.items(),
)
def test_each_public_export_resolves_to_canonical_object(
    public_name: str,
    target: tuple[str, str],
) -> None:
    module_name, attribute_name = target
    direct_module = importlib.import_module(module_name)
    direct_value = getattr(direct_module, attribute_name)

    assert getattr(exchange_package, public_name) is direct_value
    assert exchange_package.__dict__[public_name] is direct_value


def test_star_import_contains_only_declared_public_symbols() -> None:
    namespace: dict[str, Any] = {}

    exec("from src.exchange import *", namespace)

    imported_names = set(namespace).difference({"__builtins__"})

    assert imported_names == set(EXPECTED_EXPORTS)

    for public_name, target in EXPECTED_EXPORTS.items():
        module_name, attribute_name = target
        direct_value = getattr(
            importlib.import_module(module_name),
            attribute_name,
        )
        assert namespace[public_name] is direct_value


def test_dir_contains_every_declared_export() -> None:
    assert set(EXPECTED_EXPORTS).issubset(
        set(dir(exchange_package))
    )


def test_unknown_public_attribute_has_standard_error() -> None:
    with pytest.raises(
        AttributeError,
        match="has no attribute 'NotAnExchangeExport'",
    ):
        getattr(
            exchange_package,
            "NotAnExchangeExport",
        )


def test_package_import_is_lazy_in_fresh_interpreter() -> None:
    project_root = Path(__file__).resolve().parents[3]
    code = """
import sys
import src.exchange

eager_modules = {
    name
    for name in sys.modules
    if name.startswith("src.exchange.")
}
assert eager_modules == set(), eager_modules

from src.exchange import BaseExchange

assert "src.exchange.base" in sys.modules
assert "src.exchange.ccxt_exchange" not in sys.modules
assert "src.exchange.bingx_adapter" not in sys.modules
assert "src.exchange.bingx_client" not in sys.modules
"""

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        result.stdout + result.stderr
    )