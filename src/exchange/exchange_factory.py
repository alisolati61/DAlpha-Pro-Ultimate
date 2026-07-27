"""Deterministic factory for asynchronous exchange adapters."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from threading import RLock
from typing import Any, ClassVar

from src.exchange.base import BaseExchange
from src.exchange.bingx_adapter import BingXAdapter
from src.exchange.ccxt_exchange import CCXTExchange
from src.exchange.exceptions import ExchangeError

ExchangeBuilder = Callable[..., BaseExchange]


class ExchangeType(str, Enum):
    """Known exchange identifiers.

    ``PAPER`` remains reserved until its driver implements ``BaseExchange``.
    """

    BINGX = "bingx"
    BINANCE = "binance"
    BYBIT = "bybit"
    OKX = "okx"
    KUCOIN = "kucoin"
    PAPER = "paper"


def _pop_config_alias(
    config: dict[str, Any],
    canonical_name: str,
    *aliases: str,
    default: Any = None,
) -> Any:
    names = (canonical_name, *aliases)
    supplied = [name for name in names if name in config]

    if len(supplied) > 1:
        joined = ", ".join(supplied)
        raise ValueError(
            f"Conflicting exchange configuration aliases: {joined}"
        )

    if not supplied:
        return default

    return config.pop(supplied[0])


def _native_bingx_builder(**config: Any) -> BaseExchange:
    """Build the hardened native BingX adapter.

    Common CCXT-style credential aliases are accepted so existing application
    configuration does not silently break when BingX switches to the native
    adapter.
    """

    normalized = dict(config)
    api_key = _pop_config_alias(
        normalized,
        "api_key",
        "apiKey",
    )
    api_secret = _pop_config_alias(
        normalized,
        "api_secret",
        "secret",
    )
    demo_mode = _pop_config_alias(
        normalized,
        "demo_mode",
        "demoMode",
        "sandbox",
    )

    return BingXAdapter(
        api_key=api_key,
        api_secret=api_secret,
        demo_mode=demo_mode,
        **normalized,
    )


def _ccxt_builder(exchange_name: str) -> ExchangeBuilder:
    """Create a late-bound builder for one CCXT exchange."""

    def build(**config: Any) -> BaseExchange:
        return CCXTExchange(exchange_name, **config)

    return build


_DEFAULT_BUILDERS: dict[str, ExchangeBuilder] = {
    ExchangeType.BINGX.value: _native_bingx_builder,
    **{
        exchange_type.value: _ccxt_builder(exchange_type.value)
        for exchange_type in (
            ExchangeType.BINANCE,
            ExchangeType.BYBIT,
            ExchangeType.OKX,
            ExchangeType.KUCOIN,
        )
    },
}


class ExchangeFactory:
    """Create ``BaseExchange`` adapters from a controlled registry."""

    _builders: ClassVar[dict[str, ExchangeBuilder]] = dict(
        _DEFAULT_BUILDERS
    )
    _registry_lock: ClassVar[RLock] = RLock()

    @classmethod
    def create(
        cls,
        exchange_type: ExchangeType | str,
        **config: Any,
    ) -> BaseExchange:
        """Create an adapter without opening its network connection."""

        exchange_name = cls._normalize_exchange_name(exchange_type)

        with cls._registry_lock:
            builder = cls._builders.get(exchange_name)

        if builder is None:
            supported = ", ".join(cls.supported_exchanges()) or "none"
            raise ExchangeError(
                message=(
                    f"Unsupported exchange: {exchange_name}. "
                    f"Registered exchanges: {supported}"
                ),
                exchange=exchange_name,
                operation="create_exchange",
            )

        try:
            exchange = builder(**config)
        except ExchangeError:
            raise
        except Exception as exc:
            raise ExchangeError(
                message=(
                    "Failed to create exchange adapter: "
                    f"{exchange_name}"
                ),
                exchange=exchange_name,
                operation="create_exchange",
            ) from exc

        if not isinstance(exchange, BaseExchange):
            raise TypeError(
                "Exchange builder must return a BaseExchange instance: "
                f"{exchange_name}"
            )

        return exchange

    @classmethod
    def register(
        cls,
        exchange_type: ExchangeType | str,
        builder: ExchangeBuilder,
        *,
        replace: bool = False,
    ) -> None:
        """Register a builder under a normalized exchange identifier."""

        exchange_name = cls._normalize_exchange_name(exchange_type)

        if not callable(builder):
            raise TypeError("Exchange builder must be callable.")

        with cls._registry_lock:
            if exchange_name in cls._builders and not replace:
                raise ValueError(
                    "Exchange builder is already registered: "
                    f"{exchange_name}"
                )

            cls._builders[exchange_name] = builder

    @classmethod
    def unregister(
        cls,
        exchange_type: ExchangeType | str,
    ) -> ExchangeBuilder:
        """Remove and return a registered builder."""

        exchange_name = cls._normalize_exchange_name(exchange_type)

        with cls._registry_lock:
            try:
                return cls._builders.pop(exchange_name)
            except KeyError as exc:
                raise ExchangeError(
                    message=(
                        "Exchange builder is not registered: "
                        f"{exchange_name}"
                    ),
                    exchange=exchange_name,
                    operation="unregister_exchange",
                ) from exc

    @classmethod
    def is_registered(
        cls,
        exchange_type: ExchangeType | str,
    ) -> bool:
        """Return whether a builder exists for the exchange identifier."""

        exchange_name = cls._normalize_exchange_name(exchange_type)

        with cls._registry_lock:
            return exchange_name in cls._builders

    @classmethod
    def supported_exchanges(cls) -> list[str]:
        """Return registered exchange names in deterministic order."""

        with cls._registry_lock:
            return sorted(cls._builders)

    @classmethod
    def restore_defaults(cls) -> None:
        """Restore the curated production registry.

        This is useful for deterministic test isolation and controlled runtime
        reconfiguration.
        """

        with cls._registry_lock:
            cls._builders = dict(_DEFAULT_BUILDERS)

    @staticmethod
    def _normalize_exchange_name(
        exchange_type: ExchangeType | str,
    ) -> str:
        if isinstance(exchange_type, ExchangeType):
            return exchange_type.value

        if not isinstance(exchange_type, str):
            raise TypeError(
                "Exchange type must be an ExchangeType or string."
            )

        exchange_name = exchange_type.strip().casefold()

        if not exchange_name:
            raise ValueError("Exchange type cannot be empty.")

        return exchange_name


__all__ = (
    "ExchangeBuilder",
    "ExchangeFactory",
    "ExchangeType",
)