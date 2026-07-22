# src/exchange/models.py (فایل جدید)
"""
BingX-specific data models.
Clean separation from domain models for adapter pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


class BingXOrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class BingXPositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"


class BingXOrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"
    TRAILING_STOP_MARKET = "TRAILING_STOP_MARKET"


class BingXTimeInForce(str, Enum):
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    GTX = "GTX"


class BingXOrderStatus(str, Enum):
    NEW = "NEW"
    PENDING = "PENDING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass(slots=True)
class BingXBalance:
    """BingX wallet balance."""
    asset: str
    wallet_balance: Decimal
    unrealized_pnl: Decimal
    margin_balance: Decimal
    available_balance: Decimal
    max_withdraw_amount: Decimal
    
    @property
    def total_equity(self) -> Decimal:
        return self.wallet_balance + self.unrealized_pnl


@dataclass(slots=True)
class BingXPosition:
    """BingX futures position."""
    symbol: str
    position_side: BingXPositionSide
    position_amount: Decimal
    entry_price: Decimal
    mark_price: Decimal
    unrealized_pnl: Decimal
    liquidation_price: Decimal
    leverage: int
    margin_type: str  # ISOLATED or CROSSED
    isolated_margin: Optional[Decimal] = None
    
    @property
    def pnl_percent(self) -> Decimal:
        if self.entry_price == 0:
            return Decimal("0")
        return ((self.mark_price - self.entry_price) / self.entry_price * 100).quantize(Decimal("0.01"))


@dataclass(slots=True)
class BingXOrder:
    """BingX order response."""
    order_id: str
    symbol: str
    side: BingXOrderSide
    position_side: BingXPositionSide
    order_type: BingXOrderType
    status: BingXOrderStatus
    price: Decimal
    quantity: Decimal
    executed_qty: Decimal
    avg_price: Decimal
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass(slots=True)
class BingXTicker:
    """BingX 24hr ticker."""
    symbol: str
    last_price: Decimal
    price_change: Decimal
    price_change_percent: Decimal
    high_price: Decimal
    low_price: Decimal
    volume: Decimal
    quote_volume: Decimal
    bid_price: Decimal
    ask_price: Decimal
    open_time: Optional[datetime] = None
    close_time: Optional[datetime] = None


@dataclass(slots=True)
class BingXOrderBook:
    """BingX order book."""
    symbol: str
    last_update_id: int
    bids: list[tuple[Decimal, Decimal]]  # (price, quantity)
    asks: list[tuple[Decimal, Decimal]]
    
    @property
    def best_bid(self) -> Decimal:
        return self.bids[0][0] if self.bids else Decimal("0")
    
    @property
    def best_ask(self) -> Decimal:
        return self.asks[0][0] if self.asks else Decimal("0")
    
    @property
    def spread(self) -> Decimal:
        return self.best_ask - self.best_bid
    
    @property
    def mid_price(self) -> Decimal:
        return (self.best_bid + self.best_ask) / 2


@dataclass(slots=True)
class BingXKline:
    """BingX candlestick."""
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    close_time: datetime
    quote_volume: Decimal
    trades_count: int
    taker_buy_volume: Decimal
    taker_buy_quote_volume: Decimal


@dataclass(slots=True)
class BingXFundingRate:
    """BingX funding rate."""
    symbol: str
    funding_rate: Decimal
    funding_time: datetime
    mark_price: Decimal


@dataclass(slots=True)
class BingXTrade:
    """BingX recent trade."""
    trade_id: int
    price: Decimal
    quantity: Decimal
    side: BingXOrderSide
    timestamp: datetime