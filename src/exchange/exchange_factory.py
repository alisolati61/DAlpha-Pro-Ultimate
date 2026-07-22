# src/exchange/exchange_factory.py (فایل جدید)
"""
Exchange Adapter Factory.
Creates appropriate exchange adapter based on configuration.
Easily extensible for new exchanges.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Type

from src.exchange.bingx_adapter import BingXAdapter
from src.exchange.exceptions import ExchangeError
from src.interfaces.exchange_interface import ExchangeInterface
from src.logger.logger import app_logger


class ExchangeType(str, Enum):
    """Supported exchange types."""
    BINGX = "bingx"
    BINANCE = "binance"
    BYBIT = "bybit"
    OKX = "okx"
    KUCOIN = "kucoin"
    PAPER = "paper"


class ExchangeFactory:
    """
    Factory for creating exchange adapters.
    
    Usage:
        adapter = ExchangeFactory.create(ExchangeType.BINGX)
        adapter = ExchangeFactory.create("bingx", api_key="...", api_secret="...")
    """
    
    _adapters: dict[ExchangeType, Type[ExchangeInterface]] = {
        ExchangeType.BINGX: BingXAdapter,
        # Future exchanges:
        # ExchangeType.BINANCE: BinanceAdapter,
        # ExchangeType.BYBIT: BybitAdapter,
        # ExchangeType.OKX: OKXAdapter,
        ExchangeType.PAPER: None,  # Will use PaperDriver
    }
    
    @classmethod
    def create(
        cls,
        exchange_type: ExchangeType | str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        demo_mode: Optional[bool] = None,
        **kwargs,
    ) -> ExchangeInterface:
        """
        Create an exchange adapter.
        
        Args:
            exchange_type: Type of exchange
            api_key: API key (optional, falls back to env)
            api_secret: API secret (optional, falls back to env)
            demo_mode: Use demo/sandbox mode
            **kwargs: Additional exchange-specific parameters
            
        Returns:
            Configured exchange adapter
            
        Raises:
            ExchangeError: If exchange type is not supported
        """
        if isinstance(exchange_type, str):
            try:
                exchange_type = ExchangeType(exchange_type.lower())
            except ValueError:
                raise ExchangeError(
                    message=f"Unsupported exchange: {exchange_type}. "
                    f"Supported: {[e.value for e in ExchangeType]}",
                    exchange=str(exchange_type),
                )
        
        adapter_class = cls._adapters.get(exchange_type)
        
        if adapter_class is None:
            if exchange_type == ExchangeType.PAPER:
                from src.drivers.paper_driver import PaperDriver
                return PaperDriver()
            
            raise ExchangeError(
                message=f"Adapter not implemented for {exchange_type.value}",
                exchange=exchange_type.value,
            )
        
        app_logger.info(
            f"Creating {exchange_type.value.upper()} adapter | "
            f"Demo: {demo_mode}"
        )
        
        return adapter_class(
            api_key=api_key,
            api_secret=api_secret,
            demo_mode=demo_mode,
            **kwargs,
    )
    
    @classmethod
    def register(
        cls,
        exchange_type: ExchangeType,
        adapter_class: Type[ExchangeInterface],
    ) -> None:
        """Register a new exchange adapter (for plugins)."""
        cls._adapters[exchange_type] = adapter_class
        app_logger.info(f"Registered adapter for {exchange_type.value}")
    
    @classmethod
    def supported_exchanges(cls) -> list[str]:
        """Get list of supported exchange names."""
        return [e.value for e in cls._adapters.keys()]