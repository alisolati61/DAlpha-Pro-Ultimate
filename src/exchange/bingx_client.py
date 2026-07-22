# src/exchange/bingx_client.py (فایل جدید)
"""
BingX HTTP Client with HMAC-SHA256 signature authentication.
Production-ready with retry logic, rate limiting, and proper error handling.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from decimal import Decimal
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config.settings import settings
from src.exchange.exceptions import (
    AuthenticationError,
    ExchangeError,
    ExchangeNotAvailableError,
    InsufficientFundsError,
    InvalidSymbolError,
    NetworkError,
    RateLimitError,
)
from src.exchange.models import (
    BingXBalance,
    BingXFundingRate,
    BingXKline,
    BingXOrder,
    BingXOrderBook,
    BingXOrderStatus,
    BingXPosition,
    BingXTicker,
    BingXTrade,
)
from src.logger.logger import app_logger


class BingXHttpClient:
    """
    Low-level HTTP client for BingX API.
    
    Handles:
    - HMAC-SHA256 request signing
    - Automatic timestamp generation
    - Rate limiting
    - Retry logic with exponential backoff
    - Error translation to domain exceptions
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        demo_mode: Optional[bool] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or settings.exchange.BINGX_API_KEY.get_secret_value()
        self.api_secret = api_secret or settings.exchange.BINGX_API_SECRET.get_secret_value()
        self.demo_mode = demo_mode if demo_mode is not None else settings.exchange.BINGX_DEMO_MODE
        
        if self.demo_mode:
            self.base_url = settings.exchange.BINGX_DEMO_URL
        else:
            self.base_url = base_url or settings.exchange.BINGX_BASE_URL
        
        self.recv_window = settings.exchange.RECV_WINDOW
        self.timeout = settings.exchange.REQUEST_TIMEOUT
        
        # HTTP client with connection pooling
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()
        
        app_logger.info(
            f"BingX HTTP Client initialized | "
            f"Demo: {self.demo_mode} | "
            f"URL: {self.base_url}"
        )
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy initialization of HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._client
    
    def _generate_signature(self, query_string: str) -> str:
        """Generate HMAC-SHA256 signature for request authentication."""
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature
    
    def _build_query_string(self, params: dict[str, Any]) -> str:
        """Build URL-encoded query string with timestamp."""
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = self.recv_window
        
        # Sort params for consistent signing
        sorted_params = dict(sorted(params.items()))
        query_string = urlencode(sorted_params)
        return query_string
    
    def _handle_error(self, response_data: dict, status_code: int) -> None:
        """Translate BingX errors to domain exceptions."""
        code = response_data.get("code", 0)
        msg = response_data.get("msg", "Unknown error")
        
        error_map = {
            # Authentication errors
            100400: AuthenticationError,
            100401: AuthenticationError,
            100403: AuthenticationError,
            100404: AuthenticationError,
            # Rate limit
            100429: RateLimitError,
            100440: RateLimitError,
            # Invalid params / symbol
            100440: InvalidSymbolError,
            100441: InvalidSymbolError,
            100442: InvalidSymbolError,
            # Insufficient funds
            100443: InsufficientFundsError,
            100444: InsufficientFundsError,
            80014: InsufficientFundsError,
            # Order errors
            100445: ExchangeError,
            100446: ExchangeError,
            # System errors
            100500: ExchangeNotAvailableError,
            100502: ExchangeNotAvailableError,
            100503: ExchangeNotAvailableError,
        }
        
        exc_class = error_map.get(code, ExchangeError)
        
        if exc_class is RateLimitError:
            raise RateLimitError(
                message=f"BingX rate limit: {msg}",
                exchange="bingx",
                error_code=str(code),
                raw_response=response_data,
                retry_after=response_data.get("retry_after", 60),
            )
        
        raise exc_class(
            message=f"BingX error [{code}]: {msg}",
            exchange="bingx",
            error_code=str(code),
            raw_response=response_data,
        )
    
    @retry(
        retry=retry_if_exception_type((NetworkError, ExchangeNotAvailableError)),
        stop=stop_after_attempt(settings.exchange.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        signed: bool = True,
    ) -> dict[str, Any]:
        """
        Execute HTTP request to BingX API.
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body (for POST)
            signed: Whether to sign the request
            
        Returns:
            Parsed JSON response
        """
        params = params or {}
        
        url = f"{self.base_url}{endpoint}"
        headers = {}
        
        if signed:
            if not self.api_key or not self.api_secret:
                raise AuthenticationError(
                    message="API key and secret required for signed requests",
                    exchange="bingx",
                )
            
            query_string = self._build_query_string(params)
            signature = self._generate_signature(query_string)
            
            params["signature"] = signature
            headers["X-BX-APIKEY"] = self.api_key
        
        try:
            client = await self._get_client()
            
            if method.upper() == "GET":
                response = await client.get(url, params=params, headers=headers)
            elif method.upper() == "POST":
                response = await client.post(url, params=params, json=data, headers=headers)
            elif method.upper() == "DELETE":
                response = await client.delete(url, params=params, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response_data = response.json()
            
            # BingX returns 200 even for errors, check code field
            if response_data.get("code", 0) != 0:
                self._handle_error(response_data, response.status_code)
            
            return response_data
            
        except httpx.TimeoutException as exc:
            raise NetworkError(
                message=f"Request timeout: {exc}",
                exchange="bingx",
            ) from exc
        except httpx.ConnectError as exc:
            raise NetworkError(
                message=f"Connection error: {exc}",
                exchange="bingx",
            ) from exc
        except (AuthenticationError, RateLimitError, InvalidSymbolError, InsufficientFundsError):
            raise
        except Exception as exc:
            raise ExchangeError(
                message=f"Unexpected error: {exc}",
                exchange="bingx",
            ) from exc
    
    async def close(self) -> None:
        """Close HTTP client connection."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            app_logger.info("BingX HTTP client closed")
    
    # ==================== MARKET DATA METHODS ====================
    
    async def get_server_time(self) -> int:
        """Get BingX server time."""
        response = await self.request("GET", "/openApi/swap/v2/server/time", signed=False)
        return response["data"]["serverTime"]
    
    async def get_symbols(self) -> list[dict[str, Any]]:
        """Get all available trading pairs."""
        response = await self.request(
            "GET",
            "/openApi/swap/v2/quote/contracts",
            signed=False,
        )
        return response.get("data", [])
    
    async def get_ticker(self, symbol: str) -> BingXTicker:
        """Get 24hr ticker for a symbol."""
        response = await self.request(
            "GET",
            "/openApi/swap/v2/quote/ticker",
            params={"symbol": symbol},
            signed=False,
        )
        data = response["data"][0]
        
        return BingXTicker(
            symbol=data["symbol"],
            last_price=Decimal(str(data["lastPrice"])),
            price_change=Decimal(str(data.get("priceChange", 0))),
            price_change_percent=Decimal(str(data.get("priceChangePercent", 0))),
            high_price=Decimal(str(data.get("highPrice", 0))),
            low_price=Decimal(str(data.get("lowPrice", 0))),
            volume=Decimal(str(data.get("volume", 0))),
            quote_volume=Decimal(str(data.get("quoteVolume", 0))),
            bid_price=Decimal(str(data.get("bidPrice", 0))),
            ask_price=Decimal(str(data.get("askPrice", 0))),
        )
    
    async def get_orderbook(self, symbol: str, limit: int = 20) -> BingXOrderBook:
        """Get order book depth."""
        response = await self.request(
            "GET",
            "/openApi/swap/v2/quote/depth",
            params={"symbol": symbol, "limit": limit},
            signed=False,
        )
        data = response["data"]
        
        bids = [(Decimal(str(p)), Decimal(str(q))) for p, q in data.get("bids", [])]
        asks = [(Decimal(str(p)), Decimal(str(q))) for p, q in data.get("asks", [])]
        
        return BingXOrderBook(
            symbol=symbol,
            last_update_id=data.get("lastUpdateId", 0),
            bids=bids,
            asks=asks,
        )
    
    async def get_klines(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> list[BingXKline]:
        """Get historical candlestick data."""
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        
        response = await self.request(
            "GET",
            "/openApi/swap/v3/quote/klines",
            params=params,
            signed=False,
        )
        
        klines = []
        for item in response.get("data", []):
            klines.append(BingXKline(
                open_time=datetime.fromtimestamp(item[0] / 1000),
                open=Decimal(str(item[1])),
                high=Decimal(str(item[2])),
                low=Decimal(str(item[3])),
                close=Decimal(str(item[4])),
                volume=Decimal(str(item[5])),
                close_time=datetime.fromtimestamp(item[6] / 1000),
                quote_volume=Decimal(str(item[7])),
                trades_count=item[8],
                taker_buy_volume=Decimal(str(item[9])),
                taker_buy_quote_volume=Decimal(str(item[10])),
            ))
        
        return klines
    
    async def get_recent_trades(self, symbol: str, limit: int = 100) -> list[BingXTrade]:
        """Get recent trades."""
        response = await self.request(
            "GET",
            "/openApi/swap/v2/quote/trades",
            params={"symbol": symbol, "limit": limit},
            signed=False,
        )
        
        trades = []
        for item in response.get("data", []):
            trades.append(BingXTrade(
                trade_id=item.get("id", 0),
                price=Decimal(str(item.get("price", 0))),
                quantity=Decimal(str(item.get("qty", 0))),
                side=item.get("side", "BUY"),
                timestamp=datetime.fromtimestamp(item.get("time", 0) / 1000),
            ))
        
        return trades
    
    async def get_funding_rate(self, symbol: str) -> BingXFundingRate:
        """Get current funding rate."""
        response = await self.request(
            "GET",
            "/openApi/swap/v2/quote/premiumIndex",
            params={"symbol": symbol},
            signed=False,
        )
        data = response["data"][0]
        
        return BingXFundingRate(
            symbol=symbol,
            funding_rate=Decimal(str(data.get("lastFundingRate", 0))),
            funding_time=datetime.fromtimestamp(data.get("nextFundingTime", 0) / 1000),
            mark_price=Decimal(str(data.get("markPrice", 0))),
        )
    
    # ==================== ACCOUNT METHODS ====================
    
    async def get_balance(self) -> list[BingXBalance]:
        """Get futures account balance."""
        response = await self.request(
            "GET",
            "/openApi/swap/v3/user/balance",
            signed=True,
        )
        
        balances = []
        for item in response.get("data", {}).get("balance", []):
            balances.append(BingXBalance(
                asset=item.get("asset", "USDT"),
                wallet_balance=Decimal(str(item.get("walletBalance", 0))),
                unrealized_pnl=Decimal(str(item.get("unrealizedProfit", 0))),
                margin_balance=Decimal(str(item.get("marginBalance", 0))),
                available_balance=Decimal(str(item.get("availableBalance", 0))),
                max_withdraw_amount=Decimal(str(item.get("maxWithdrawAmount", 0))),
            ))
        
        return balances
    
    async def get_positions(self, symbol: Optional[str] = None) -> list[BingXPosition]:
        """Get open positions."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        
        response = await self.request(
            "GET",
            "/openApi/swap/v2/user/positions",
            params=params,
            signed=True,
        )
        
        positions = []
        for item in response.get("data", []):
            positions.append(BingXPosition(
                symbol=item.get("symbol", ""),
                position_side=item.get("positionSide", "BOTH"),
                position_amount=Decimal(str(item.get("positionAmt", 0))),
                entry_price=Decimal(str(item.get("entryPrice", 0))),
                mark_price=Decimal(str(item.get("markPrice", 0))),
                unrealized_pnl=Decimal(str(item.get("unrealizedProfit", 0))),
                liquidation_price=Decimal(str(item.get("liquidationPrice", 0))),
                leverage=int(item.get("leverage", 1)),
                margin_type=item.get("marginType", "CROSSED"),
                isolated_margin=Decimal(str(item.get("isolatedMargin", 0))) if item.get("isolatedMargin") else None,
            ))
        
        return positions
    
    # ==================== TRADING METHODS ====================
    
    async def place_order(
        self,
        symbol: str,
        side: str,
        position_side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
        time_in_force: str = "GTC",
        client_order_id: Optional[str] = None,
    ) -> BingXOrder:
        """Place a new order."""
        params = {
            "symbol": symbol,
            "side": side,
            "positionSide": position_side,
            "type": order_type,
            "quantity": str(quantity),
        }
        
        if price is not None:
            params["price"] = str(price)
        if stop_price is not None:
            params["stopPrice"] = str(stop_price)
        if stop_loss is not None:
            params["stopLoss"] = str(stop_loss)
        if take_profit is not None:
            params["takeProfit"] = str(take_profit)
        if time_in_force:
            params["timeInForce"] = time_in_force
        if client_order_id:
            params["newClientOrderId"] = client_order_id
        
        response = await self.request(
            "POST",
            "/openApi/swap/v2/trade/order",
            params=params,
            signed=True,
        )
        
        data = response["data"]["order"]
        
        return BingXOrder(
            order_id=data.get("orderId", ""),
            symbol=data.get("symbol", ""),
            side=data.get("side", "BUY"),
            position_side=data.get("positionSide", "BOTH"),
            order_type=data.get("type", "MARKET"),
            status=BingXOrderStatus(data.get("status", "NEW")),
            price=Decimal(str(data.get("price", 0))),
            quantity=Decimal(str(data.get("origQty", 0))),
            executed_qty=Decimal(str(data.get("executedQty", 0))),
            avg_price=Decimal(str(data.get("avgPrice", 0))),
        )
    
    async def cancel_order(self, symbol: str, order_id: str) -> dict[str, Any]:
        """Cancel an order."""
        return await self.request(
            "DELETE",
            "/openApi/swap/v2/trade/order",
            params={"symbol": symbol, "orderId": order_id},
            signed=True,
        )
    
    async def cancel_all_orders(self, symbol: str) -> dict[str, Any]:
        """Cancel all orders for a symbol."""
        return await self.request(
            "DELETE",
            "/openApi/swap/v2/trade/allOpenOrders",
            params={"symbol": symbol},
            signed=True,
        )
    
    async def get_order(self, symbol: str, order_id: str) -> BingXOrder:
        """Get order status."""
        response = await self.request(
            "GET",
            "/openApi/swap/v2/trade/order",
            params={"symbol": symbol, "orderId": order_id},
            signed=True,
        )
        
        data = response["data"]["order"]
        
        return BingXOrder(
            order_id=data.get("orderId", ""),
            symbol=data.get("symbol", ""),
            side=data.get("side", "BUY"),
            position_side=data.get("positionSide", "BOTH"),
            order_type=data.get("type", "MARKET"),
            status=BingXOrderStatus(data.get("status", "NEW")),
            price=Decimal(str(data.get("price", 0))),
            quantity=Decimal(str(data.get("origQty", 0))),
            executed_qty=Decimal(str(data.get("executedQty", 0))),
            avg_price=Decimal(str(data.get("avgPrice", 0))),
            stop_loss=Decimal(str(data.get("stopLoss", 0))) if data.get("stopLoss") else None,
            take_profit=Decimal(str(data.get("takeProfit", 0))) if data.get("takeProfit") else None,
        )
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> list[BingXOrder]:
        """Get all open orders."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        
        response = await self.request(
            "GET",
            "/openApi/swap/v2/trade/openOrders",
            params=params,
            signed=True,
        )
        
        orders = []
        for item in response.get("data", {}).get("orders", []):
            orders.append(BingXOrder(
                order_id=item.get("orderId", ""),
                symbol=item.get("symbol", ""),
                side=item.get("side", "BUY"),
                position_side=item.get("positionSide", "BOTH"),
                order_type=item.get("type", "MARKET"),
                status=BingXOrderStatus(item.get("status", "NEW")),
                price=Decimal(str(item.get("price", 0))),
                quantity=Decimal(str(item.get("origQty", 0))),
                executed_qty=Decimal(str(item.get("executedQty", 0))),
                avg_price=Decimal(str(item.get("avgPrice", 0))),
            ))
        
        return orders
    
    async def set_leverage(self, symbol: str, leverage: int, position_side: str = "BOTH") -> dict[str, Any]:
        """Set leverage for a symbol."""
        return await self.request(
            "POST",
            "/openApi/swap/v2/trade/leverage",
            params={
                "symbol": symbol,
                "leverage": leverage,
                "positionSide": position_side,
            },
            signed=True,
        )
    
    async def set_margin_type(self, symbol: str, margin_type: str) -> dict[str, Any]:
        """Set margin type (ISOLATED or CROSSED)."""
        return await self.request(
            "POST",
            "/openApi/swap/v2/trade/marginType",
            params={
                "symbol": symbol,
                "marginType": margin_type,
            },
            signed=True,
        )
    
    async def get_position_mode(self) -> str:
        """Get current position mode (ONE_WAY or HEDGE)."""
        response = await self.request(
            "GET",
            "/openApi/swap/v2/user/positionMode",
            signed=True,
        )
        return response["data"].get("positionMode", "ONE_WAY")
    
    async def set_position_mode(self, mode: str) -> dict[str, Any]:
        """Set position mode."""
        return await self.request(
            "POST",
            "/openApi/swap/v2/user/positionMode",
            params={"positionMode": mode},
            signed=True,
        )
    
    async def close_all_positions(self, symbol: Optional[str] = None) -> dict[str, Any]:
        """Close all positions."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        
        return await self.request(
            "POST",
            "/openApi/swap/v2/trade/closeAllPositions",
            params=params,
            signed=True,
        )