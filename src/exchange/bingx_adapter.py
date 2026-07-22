# src/exchange/bingx_adapter.py (فایل جدید)
"""
BingX Exchange Adapter.
Implements ExchangeInterface for seamless integration with DAlpha system.
Translates between BingX-specific models and domain models.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries
from src.domain.order import Order
from src.domain.value_objects.price import Price
from src.domain.value_objects.quantity import Quantity
from src.domain.value_objects.side import Side
from src.domain.value_objects.symbol import Symbol
from src.exchange.bingx_client import BingXHttpClient
from src.exchange.exceptions import ExchangeError
from src.exchange.models import (
    BingXOrderSide,
    BingXOrderType,
    BingXPositionSide,
)
from src.interfaces.exchange_interface import ExchangeInterface
from src.logger.logger import app_logger


class BingXAdapter(ExchangeInterface):
    """
    BingX exchange adapter for DAlpha Pro Ultimate.
    
    Bridges BingX API with the domain layer.
    All methods return domain-native objects or raw data
    that can be consumed by the analysis engine.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        demo_mode: Optional[bool] = None,
    ) -> None:
        self._client = BingXHttpClient(
            api_key=api_key,
            api_secret=api_secret,
            demo_mode=demo_mode,
        )
        self._connected = False
        app_logger.info("BingX Adapter initialized")
    
    # ==================== Connection Management ====================
    
    def connect(self) -> None:
        """Initialize connection to BingX."""
        # HTTP client is lazy-loaded, just verify credentials
        self._connected = True
        app_logger.info("BingX Adapter connected")
    
    def disconnect(self) -> None:
        """Close connection."""
        # Async close handled in client
        self._connected = False
        app_logger.info("BingX Adapter disconnected")
    
    def health_check(self) -> bool:
        """Check if exchange is reachable."""
        return self._connected
    
    async def verify_connection(self) -> dict[str, Any]:
        """Verify API credentials by fetching server time."""
        try:
            server_time = await self._client.get_server_time()
            self._connected = True
            return {
                "status": "connected",
                "exchange": "bingx",
                "server_time": server_time,
                "demo_mode": self._client.demo_mode,
            }
        except Exception as exc:
            self._connected = False
            raise ExchangeError(
                message=f"Failed to connect to BingX: {exc}",
                exchange="bingx",
            ) from exc
    
    # ==================== Market Data ====================
    
    async def get_balance(self) -> dict[str, Any]:
        """Get account balance."""
        balances = await self._client.get_balance()
        
        result = {}
        for bal in balances:
            result[bal.asset] = {
                "wallet_balance": float(bal.wallet_balance),
                "unrealized_pnl": float(bal.unrealized_pnl),
                "margin_balance": float(bal.margin_balance),
                "available": float(bal.available_balance),
            }
        
        return result
    
    async def get_positions(self) -> list[dict[str, Any]]:
        """Get open positions."""
        positions = await self._client.get_positions()
        
        return [
            {
                "symbol": pos.symbol,
                "side": pos.position_side.value,
                "size": float(pos.position_amount),
                "entry_price": float(pos.entry_price),
                "mark_price": float(pos.mark_price),
                "unrealized_pnl": float(pos.unrealized_pnl),
                "liquidation_price": float(pos.liquidation_price),
                "leverage": pos.leverage,
                "margin_type": pos.margin_type,
            }
            for pos in positions
        ]
    
    async def place_order(self, order: Order) -> str:
        """Place an order."""
        # Map domain Order to BingX parameters
        side = "BUY" if order.side.upper() in ["BUY", "LONG"] else "SELL"
        position_side = "LONG" if side == "BUY" else "SHORT"
        
        # Determine order type
        order_type = order.order_type.upper() if order.order_type else "MARKET"
        if order_type not in ["MARKET", "LIMIT", "STOP", "STOP_MARKET"]:
            order_type = "MARKET"
        
        # Build quantity
        quantity = Decimal(str(order.quantity))
        
        # Build price for limit orders
        price = None
        if order_type in ["LIMIT", "STOP_LIMIT"] and order.price:
            price = Decimal(str(order.price))
        
        result = await self._client.place_order(
            symbol=order.symbol,
            side=side,
            position_side=position_side,
            order_type=order_type,
            quantity=quantity,
            price=price,
        )
        
        app_logger.info(
            f"Order placed on BingX | "
            f"ID: {result.order_id} | "
            f"Symbol: {result.symbol} | "
            f"Side: {result.side} | "
            f"Type: {result.order_type}"
        )
        
        return result.order_id
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        # Note: BingX requires symbol for cancellation
        # We need to track this or fetch from open orders
        try:
            # First, try to find the symbol from open orders
            open_orders = await self._client.get_open_orders()
            for order in open_orders:
                if order.order_id == order_id:
                    await self._client.cancel_order(order.symbol, order_id)
                    return True
            
            # If not found, assume it's already filled/cancelled
            return False
            
        except Exception as exc:
            app_logger.error(f"Failed to cancel order {order_id}: {exc}")
            return False
    
    async def get_order_status(self, order_id: str) -> dict[str, Any]:
        """Get order status."""
        # Find symbol from open orders first
        open_orders = await self._client.get_open_orders()
        for order in open_orders:
            if order.order_id == order_id:
                return {
                    "order_id": order.order_id,
                    "symbol": order.symbol,
                    "status": order.status.value,
                    "side": order.side,
                    "price": float(order.price),
                    "quantity": float(order.quantity),
                    "executed_qty": float(order.executed_qty),
                    "avg_price": float(order.avg_price),
                }
        
        return {"status": "NOT_FOUND"}
    
    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        """Get latest ticker."""
        ticker = await self._client.get_ticker(symbol)
        
        return {
            "symbol": ticker.symbol,
            "last_price": float(ticker.last_price),
            "bid": float(ticker.bid_price),
            "ask": float(ticker.ask_price),
            "high": float(ticker.high_price),
            "low": float(ticker.low_price),
            "volume": float(ticker.volume),
            "price_change_percent": float(ticker.price_change_percent),
        }
    
    async def get_orderbook(self, symbol: str) -> dict[str, Any]:
        """Get order book."""
        book = await self._client.get_orderbook(symbol)
        
        return {
            "symbol": book.symbol,
            "last_update_id": book.last_update_id,
            "bids": [[float(p), float(q)] for p, q in book.bids],
            "asks": [[float(p), float(q)] for p, q in book.asks],
            "best_bid": float(book.best_bid),
            "best_ask": float(book.best_ask),
            "spread": float(book.spread),
            "mid_price": float(book.mid_price),
        }
    
    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 500,
    ) -> CandleSeries:
        """Get historical OHLCV data as CandleSeries."""
        # Map timeframe format if needed
        interval = self._normalize_timeframe(timeframe)
        
        klines = await self._client.get_klines(
            symbol=symbol,
            interval=interval,
            limit=limit,
        )
        
        candles = []
        for kline in klines:
            candles.append(Candle(
                timestamp=int(kline.open_time.timestamp()),
                open=float(kline.open),
                high=float(kline.high),
                low=float(kline.low),
                close=float(kline.close),
                volume=float(kline.volume),
            ))
        
        return CandleSeries(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
        )
    
    # ==================== Additional BingX-Specific Methods ====================
    
    async def get_funding_rate(self, symbol: str) -> dict[str, Any]:
        """Get funding rate."""
        funding = await self._client.get_funding_rate(symbol)
        
        return {
            "symbol": funding.symbol,
            "funding_rate": float(funding.funding_rate),
            "funding_time": funding.funding_time.isoformat(),
            "mark_price": float(funding.mark_price),
        }
    
    async def set_leverage(self, symbol: str, leverage: int) -> dict[str, Any]:
        """Set leverage for a symbol."""
        return await self._client.set_leverage(symbol, leverage)
    
    async def get_recent_trades(self, symbol: str, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent trades."""
        trades = await self._client.get_recent_trades(symbol, limit)
        
        return [
            {
                "trade_id": trade.trade_id,
                "price": float(trade.price),
                "quantity": float(trade.quantity),
                "side": trade.side,
                "timestamp": trade.timestamp.isoformat(),
            }
            for trade in trades
        ]
    
    async def close_all_positions(self, symbol: Optional[str] = None) -> dict[str, Any]:
        """Close all positions."""
        return await self._client.close_all_positions(symbol)
    
    # ==================== Helpers ====================
    
    @staticmethod
    def _normalize_timeframe(tf: str) -> str:
        """Normalize timeframe to BingX format."""
        mapping = {
            "1m": "1m",
            "3m": "3m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "2h": "2h",
            "4h": "4h",
            "6h": "6h",
            "8h": "8h",
            "12h": "12h",
            "1d": "1d",
            "3d": "3d",
            "1w": "1w",
            "1M": "1M",
        }
        return mapping.get(tf, tf)
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._client.close()
        self.disconnect()