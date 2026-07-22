# src/exchange/bingx_websocket.py (فایل جدید)
"""
BingX WebSocket Client for real-time market data.
Supports both public market streams and private account streams.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Awaitable, Callable, Optional

import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatusCode

from src.config.settings import settings
from src.exchange.exceptions import NetworkError, WebSocketError
from src.logger.logger import app_logger


class BingXStreamType(str, Enum):
    """Available WebSocket stream types."""
    TRADE = "trade"
    KLINE = "kline"
    DEPTH = "depth"
    TICKER = "ticker"
    BOOK_TICKER = "bookTicker"
    FORCE_ORDER = "forceOrder"


@dataclass
class BingXWebSocketConfig:
    """WebSocket configuration."""
    base_url: str = "wss://open-api-ws.bingx.com/market"
    heartbeat_interval: int = field(default_factory=lambda: settings.exchange.WS_HEARTBEAT_INTERVAL)
    reconnect_delay: int = field(default_factory=lambda: settings.exchange.WS_RECONNECT_DELAY)
    max_reconnect_attempts: int = field(default_factory=lambda: settings.exchange.WS_MAX_RECONNECT_ATTEMPTS)
    auto_reconnect: bool = True


class BingXWebSocketClient:
    """
    BingX WebSocket client for real-time data.
    
    Features:
    - Automatic reconnection with exponential backoff
    - Heartbeat/ping-pong handling
    - Multiple stream subscription
    - Async callback system
    """
    
    def __init__(
        self,
        config: Optional[BingXWebSocketConfig] = None,
    ) -> None:
        self.config = config or BingXWebSocketConfig()
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._subscribed_streams: set[str] = set()
        self._callbacks: dict[str, list[Callable[[dict], Awaitable[None]]]] = {}
        self._reconnect_count = 0
        self._last_pong = time.time()
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._listen_task: Optional[asyncio.Task] = None
    
    # ==================== Connection Management ====================
    
    async def connect(self) -> None:
        """Establish WebSocket connection."""
        try:
            app_logger.info(f"Connecting to BingX WebSocket: {self.config.base_url}")
            
            self._ws = await websockets.connect(
                self.config.base_url,
                ping_interval=None,  # We handle heartbeat manually
                ping_timeout=None,
            )
            
            self._running = True
            self._reconnect_count = 0
            self._last_pong = time.time()
            
            # Start background tasks
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self._listen_task = asyncio.create_task(self._listen_loop())
            
            # Resubscribe to previous streams
            if self._subscribed_streams:
                await self._resubscribe()
            
            app_logger.info("BingX WebSocket connected successfully")
            
        except Exception as exc:
            raise WebSocketError(
                message=f"Failed to connect: {exc}",
                exchange="bingx",
            ) from exc
    
    async def disconnect(self) -> None:
        """Close WebSocket connection gracefully."""
        self._running = False
        
        # Cancel background tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        
        self._ws = None
        app_logger.info("BingX WebSocket disconnected")
    
    async def _reconnect(self) -> None:
        """Attempt to reconnect with backoff."""
        if not self.config.auto_reconnect:
            return
        
        if self._reconnect_count >= self.config.max_reconnect_attempts:
            app_logger.error("Max reconnection attempts reached")
            self._running = False
            return
        
        self._reconnect_count += 1
        delay = min(
            self.config.reconnect_delay * (2 ** (self._reconnect_count - 1)),
            60,  # Max 60 seconds
        )
        
        app_logger.warning(
            f"Reconnecting in {delay}s... "
            f"(attempt {self._reconnect_count}/{self.config.max_reconnect_attempts})"
        )
        
        await asyncio.sleep(delay)
        
        try:
            await self.connect()
        except Exception as exc:
            app_logger.error(f"Reconnection failed: {exc}")
    
    # ==================== Subscription Management ====================
    
    async def subscribe(self, stream: str) -> None:
        """Subscribe to a stream."""
        if not self._ws or not self._running:
            raise WebSocketError(
                message="WebSocket not connected",
                exchange="bingx",
            )
        
        subscribe_msg = {
            "id": f"sub_{int(time.time() * 1000)}",
            "reqType": "sub",
            "dataType": stream,
        }
        
        await self._ws.send(json.dumps(subscribe_msg))
        self._subscribed_streams.add(stream)
        
        app_logger.info(f"Subscribed to: {stream}")
    
    async def unsubscribe(self, stream: str) -> None:
        """Unsubscribe from a stream."""
        if not self._ws or not self._running:
            return
        
        unsubscribe_msg = {
            "id": f"unsub_{int(time.time() * 1000)}",
            "reqType": "unsub",
            "dataType": stream,
        }
        
        await self._ws.send(json.dumps(unsubscribe_msg))
        self._subscribed_streams.discard(stream)
        
        app_logger.info(f"Unsubscribed from: {stream}")
    
    async def _resubscribe(self) -> None:
        """Resubscribe to all previous streams after reconnection."""
        for stream in self._subscribed_streams:
            await self.subscribe(stream)
    
    # ==================== Callback System ====================
    
    def on(self, event_type: str, callback: Callable[[dict], Awaitable[None]]) -> None:
        """Register callback for event type."""
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)
    
    def off(self, event_type: str, callback: Callable[[dict], Awaitable[None]]) -> None:
        """Remove callback for event type."""
        if event_type in self._callbacks:
            self._callbacks[event_type] = [cb for cb in self._callbacks[event_type] if cb != callback]
    
    async def _dispatch(self, event_type: str, data: dict) -> None:
        """Dispatch event to registered callbacks."""
        callbacks = self._callbacks.get(event_type, [])
        for callback in callbacks:
            try:
                await callback(data)
            except Exception as exc:
                app_logger.error(f"Callback error for {event_type}: {exc}")
    
    # ==================== Convenience Methods ====================
    
    async def subscribe_trade(self, symbol: str) -> None:
        """Subscribe to trade stream."""
        await self.subscribe(f"{symbol}@trade")
    
    async def subscribe_kline(self, symbol: str, interval: str = "1m") -> None:
        """Subscribe to kline/candlestick stream."""
        await self.subscribe(f"{symbol}@kline_{interval}")
    
    async def subscribe_depth(self, symbol: str, level: int = 20) -> None:
        """Subscribe to order book depth."""
        await self.subscribe(f"{symbol}@depth{level}")
    
    async def subscribe_ticker(self, symbol: str) -> None:
        """Subscribe to 24hr ticker."""
        await self.subscribe(f"{symbol}@ticker")
    
    async def subscribe_book_ticker(self, symbol: str) -> None:
        """Subscribe to best bid/ask."""
        await self.subscribe(f"{symbol}@bookTicker")
    
    # ==================== Background Loops ====================
    
    async def _heartbeat_loop(self) -> None:
        """Send periodic ping to keep connection alive."""
        while self._running:
            try:
                if self._ws and not self._ws.closed:
                    ping_msg = {"id": f"ping_{int(time.time() * 1000)}", "reqType": "ping"}
                    await self._ws.send(json.dumps(ping_msg))
                
                await asyncio.sleep(self.config.heartbeat_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as exc:
                app_logger.warning(f"Heartbeat error: {exc}")
    
    async def _listen_loop(self) -> None:
        """Main message listening loop."""
        while self._running:
            try:
                if not self._ws or self._ws.closed:
                    await self._reconnect()
                    if not self._running:
                        break
                    continue
                
                message = await self._ws.recv()
                await self._handle_message(message)
                
            except ConnectionClosed:
                app_logger.warning("WebSocket connection closed")
                await self._reconnect()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                app_logger.error(f"Listen error: {exc}")
                await asyncio.sleep(1)
    
    async def _handle_message(self, raw_message: str) -> None:
        """Parse and handle incoming WebSocket message."""
        try:
            data = json.loads(raw_message)
            
            # Handle pong response
            if data.get("dataType") == "PONG":
                self._last_pong = time.time()
                return
            
            # Extract data type
            data_type = data.get("dataType", "")
            
            # Parse based on data type
            if "@trade" in data_type:
                parsed = self._parse_trade(data)
                await self._dispatch("trade", parsed)
            elif "@kline_" in data_type:
                parsed = self._parse_kline(data)
                await self._dispatch("kline", parsed)
            elif "@depth" in data_type:
                parsed = self._parse_depth(data)
                await self._dispatch("depth", parsed)
            elif "@ticker" in data_type:
                parsed = self._parse_ticker(data)
                await self._dispatch("ticker", parsed)
            elif "@bookTicker" in data_type:
                parsed = self._parse_book_ticker(data)
                await self._dispatch("book_ticker", parsed)
            else:
                await self._dispatch("raw", data)
                
        except json.JSONDecodeError:
            app_logger.warning(f"Invalid JSON received: {raw_message[:200]}")
        except Exception as exc:
            app_logger.error(f"Message handling error: {exc}")
    
    # ==================== Message Parsers ====================
    
    def _parse_trade(self, data: dict) -> dict:
        """Parse trade message."""
        trade_data = data.get("data", [{}])[0]
        return {
            "event_type": "trade",
            "symbol": data.get("dataType", "").split("@")[0],
            "trade_id": trade_data.get("t"),
            "price": float(trade_data.get("p", 0)),
            "quantity": float(trade_data.get("q", 0)),
            "side": "BUY" if trade_data.get("m") == False else "SELL",
            "timestamp": trade_data.get("T"),
        }
    
    def _parse_kline(self, data: dict) -> dict:
        """Parse kline/candlestick message."""
        kline_data = data.get("data", [{}])[0].get("k", {})
        return {
            "event_type": "kline",
            "symbol": kline_data.get("s"),
            "interval": kline_data.get("i"),
            "open_time": kline_data.get("t"),
            "close_time": kline_data.get("T"),
            "open": float(kline_data.get("o", 0)),
            "high": float(kline_data.get("h", 0)),
            "low": float(kline_data.get("l", 0)),
            "close": float(kline_data.get("c", 0)),
            "volume": float(kline_data.get("v", 0)),
            "is_closed": kline_data.get("x", False),
        }
    
    def _parse_depth(self, data: dict) -> dict:
        """Parse order book depth message."""
        depth_data = data.get("data", {})
        return {
            "event_type": "depth",
            "symbol": data.get("dataType", "").split("@")[0],
            "last_update_id": depth_data.get("u"),
            "bids": [[float(p), float(q)] for p, q in depth_data.get("b", [])],
            "asks": [[float(p), float(q)] for p, q in depth_data.get("a", [])],
        }
    
    def _parse_ticker(self, data: dict) -> dict:
        """Parse 24hr ticker message."""
        ticker_data = data.get("data", [{}])[0]
        return {
            "event_type": "ticker",
            "symbol": ticker_data.get("s"),
            "last_price": float(ticker_data.get("c", 0)),
            "price_change": float(ticker_data.get("p", 0)),
            "price_change_percent": float(ticker_data.get("P", 0)),
            "high": float(ticker_data.get("h", 0)),
            "low": float(ticker_data.get("l", 0)),
            "volume": float(ticker_data.get("v", 0)),
            "quote_volume": float(ticker_data.get("q", 0)),
        }
    
    def _parse_book_ticker(self, data: dict) -> dict:
        """Parse best bid/ask message."""
        book_data = data.get("data", {})
        return {
            "event_type": "book_ticker",
            "symbol": book_data.get("s"),
            "best_bid": float(book_data.get("b", 0)),
            "best_bid_qty": float(book_data.get("B", 0)),
            "best_ask": float(book_data.get("a", 0)),
            "best_ask_qty": float(book_data.get("A", 0)),
        }
    
    # ==================== Context Manager ====================
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()