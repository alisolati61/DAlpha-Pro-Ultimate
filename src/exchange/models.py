"""Validated BingX transport models.

These models are exchange-boundary DTOs. They deliberately remain separate
from domain entities while normalizing BingX payload values into predictable
Python types.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, TypeVar

_EnumT = TypeVar("_EnumT", bound=Enum)
_ZERO = Decimal("0")
_PERCENT_QUANTUM = Decimal("0.01")


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


def _required_text(
    value: Any,
    *,
    field_name: str,
    uppercase: bool = False,
) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{field_name} cannot be empty.")

    return normalized.upper() if uppercase else normalized


def _enum_value(
    enum_type: type[_EnumT],
    value: _EnumT | str,
    *,
    field_name: str,
) -> _EnumT:
    if isinstance(value, enum_type):
        return value

    if not isinstance(value, str):
        raise TypeError(
            f"{field_name} must be a {enum_type.__name__} or string."
        )

    normalized = value.strip().upper()

    try:
        return enum_type(normalized)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(
            f"Unsupported {field_name}: {value!r}. "
            f"Allowed values: {allowed}"
        ) from exc


def _decimal_value(
    value: Any,
    *,
    field_name: str,
    minimum: Decimal | None = None,
    strictly_positive: bool = False,
) -> Decimal:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be numeric.")

    try:
        normalized = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} must be numeric.") from exc

    if not normalized.is_finite():
        raise ValueError(f"{field_name} must be finite.")

    if strictly_positive and normalized <= _ZERO:
        raise ValueError(f"{field_name} must be greater than zero.")

    if minimum is not None and normalized < minimum:
        raise ValueError(
            f"{field_name} must be greater than or equal to {minimum}."
        )

    return normalized


def _integer_value(
    value: Any,
    *,
    field_name: str,
    minimum: int = 0,
) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer.")

    if isinstance(value, int):
        normalized = value
    elif isinstance(value, str):
        stripped = value.strip()

        if not stripped:
            raise ValueError(f"{field_name} cannot be empty.")

        try:
            normalized = int(stripped)
        except ValueError as exc:
            raise TypeError(
                f"{field_name} must be an integer."
            ) from exc
    else:
        raise TypeError(f"{field_name} must be an integer.")

    if normalized < minimum:
        raise ValueError(
            f"{field_name} must be greater than or equal to {minimum}."
        )

    return normalized


def _utc_datetime(
    value: datetime | int | float | None,
    *,
    field_name: str,
) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, bool):
        raise TypeError(
            f"{field_name} must be a datetime or Unix timestamp."
        )

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)

    if isinstance(value, (int, float)):
        normalized = float(value)

        if not math.isfinite(normalized):
            raise ValueError(f"{field_name} timestamp must be finite.")

        # BingX timestamps are normally milliseconds. Small values are treated
        # as seconds to keep the models useful with standard Unix timestamps.
        seconds = normalized / 1000 if abs(normalized) >= 10_000_000_000 else normalized
        return datetime.fromtimestamp(seconds, tz=UTC)

    raise TypeError(
        f"{field_name} must be a datetime or Unix timestamp."
    )


def _normalize_levels(
    levels: list[tuple[Any, Any]],
    *,
    field_name: str,
    reverse: bool,
) -> list[tuple[Decimal, Decimal]]:
    if not isinstance(levels, list):
        raise TypeError(f"{field_name} must be a list.")

    normalized: list[tuple[Decimal, Decimal]] = []

    for index, level in enumerate(levels):
        if not isinstance(level, (tuple, list)) or len(level) != 2:
            raise TypeError(
                f"{field_name}[{index}] must contain price and quantity."
            )

        price = _decimal_value(
            level[0],
            field_name=f"{field_name}[{index}].price",
            strictly_positive=True,
        )
        quantity = _decimal_value(
            level[1],
            field_name=f"{field_name}[{index}].quantity",
            minimum=_ZERO,
        )
        normalized.append((price, quantity))

    normalized.sort(key=lambda item: item[0], reverse=reverse)
    return normalized


@dataclass(frozen=True, slots=True)
class BingXBalance:
    """BingX wallet balance."""

    asset: str
    wallet_balance: Decimal
    unrealized_pnl: Decimal
    margin_balance: Decimal
    available_balance: Decimal
    max_withdraw_amount: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "asset",
            _required_text(
                self.asset,
                field_name="asset",
                uppercase=True,
            ),
        )

        for field_name in (
            "wallet_balance",
            "unrealized_pnl",
            "margin_balance",
            "available_balance",
        ):
            object.__setattr__(
                self,
                field_name,
                _decimal_value(
                    getattr(self, field_name),
                    field_name=field_name,
                ),
            )

        object.__setattr__(
            self,
            "max_withdraw_amount",
            _decimal_value(
                self.max_withdraw_amount,
                field_name="max_withdraw_amount",
                minimum=_ZERO,
            ),
        )

    @property
    def total_equity(self) -> Decimal:
        return self.wallet_balance + self.unrealized_pnl


@dataclass(frozen=True, slots=True)
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
    margin_type: str
    isolated_margin: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "symbol",
            _required_text(self.symbol, field_name="symbol"),
        )
        object.__setattr__(
            self,
            "position_side",
            _enum_value(
                BingXPositionSide,
                self.position_side,
                field_name="position_side",
            ),
        )
        object.__setattr__(
            self,
            "position_amount",
            _decimal_value(
                self.position_amount,
                field_name="position_amount",
            ),
        )

        for field_name in (
            "entry_price",
            "mark_price",
            "liquidation_price",
        ):
            object.__setattr__(
                self,
                field_name,
                _decimal_value(
                    getattr(self, field_name),
                    field_name=field_name,
                    minimum=_ZERO,
                ),
            )

        object.__setattr__(
            self,
            "unrealized_pnl",
            _decimal_value(
                self.unrealized_pnl,
                field_name="unrealized_pnl",
            ),
        )
        object.__setattr__(
            self,
            "leverage",
            _integer_value(
                self.leverage,
                field_name="leverage",
                minimum=1,
            ),
        )
        object.__setattr__(
            self,
            "margin_type",
            _required_text(
                self.margin_type,
                field_name="margin_type",
                uppercase=True,
            ),
        )

        if self.isolated_margin is not None:
            object.__setattr__(
                self,
                "isolated_margin",
                _decimal_value(
                    self.isolated_margin,
                    field_name="isolated_margin",
                    minimum=_ZERO,
                ),
            )

    @property
    def pnl_percent(self) -> Decimal:
        if self.entry_price == _ZERO:
            return _ZERO

        change = (
            (self.mark_price - self.entry_price)
            / self.entry_price
            * Decimal("100")
        )

        is_short = (
            self.position_side is BingXPositionSide.SHORT
            or (
                self.position_side is BingXPositionSide.BOTH
                and self.position_amount < _ZERO
            )
        )

        if is_short:
            change = -change

        return change.quantize(_PERCENT_QUANTUM)


@dataclass(frozen=True, slots=True)
class BingXOrder:
    """Normalized BingX order response."""

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
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "order_id",
            _required_text(self.order_id, field_name="order_id"),
        )
        object.__setattr__(
            self,
            "symbol",
            _required_text(self.symbol, field_name="symbol"),
        )
        object.__setattr__(
            self,
            "side",
            _enum_value(
                BingXOrderSide,
                self.side,
                field_name="side",
            ),
        )
        object.__setattr__(
            self,
            "position_side",
            _enum_value(
                BingXPositionSide,
                self.position_side,
                field_name="position_side",
            ),
        )
        object.__setattr__(
            self,
            "order_type",
            _enum_value(
                BingXOrderType,
                self.order_type,
                field_name="order_type",
            ),
        )
        object.__setattr__(
            self,
            "status",
            _enum_value(
                BingXOrderStatus,
                self.status,
                field_name="status",
            ),
        )

        for field_name in (
            "price",
            "quantity",
            "executed_qty",
            "avg_price",
        ):
            object.__setattr__(
                self,
                field_name,
                _decimal_value(
                    getattr(self, field_name),
                    field_name=field_name,
                    minimum=_ZERO,
                ),
            )

        for field_name in ("stop_loss", "take_profit"):
            value = getattr(self, field_name)

            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    _decimal_value(
                        value,
                        field_name=field_name,
                        minimum=_ZERO,
                    ),
                )

        object.__setattr__(
            self,
            "created_at",
            _utc_datetime(
                self.created_at,
                field_name="created_at",
            ),
        )
        object.__setattr__(
            self,
            "updated_at",
            _utc_datetime(
                self.updated_at,
                field_name="updated_at",
            ),
        )


@dataclass(frozen=True, slots=True)
class BingXTicker:
    """Normalized BingX 24-hour ticker."""

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
    open_time: datetime | None = None
    close_time: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "symbol",
            _required_text(self.symbol, field_name="symbol"),
        )

        for field_name in (
            "last_price",
            "high_price",
            "low_price",
            "volume",
            "quote_volume",
            "bid_price",
            "ask_price",
        ):
            object.__setattr__(
                self,
                field_name,
                _decimal_value(
                    getattr(self, field_name),
                    field_name=field_name,
                    minimum=_ZERO,
                ),
            )

        for field_name in (
            "price_change",
            "price_change_percent",
        ):
            object.__setattr__(
                self,
                field_name,
                _decimal_value(
                    getattr(self, field_name),
                    field_name=field_name,
                ),
            )

        object.__setattr__(
            self,
            "open_time",
            _utc_datetime(
                self.open_time,
                field_name="open_time",
            ),
        )
        object.__setattr__(
            self,
            "close_time",
            _utc_datetime(
                self.close_time,
                field_name="close_time",
            ),
        )


@dataclass(frozen=True, slots=True)
class BingXOrderBook:
    """Normalized BingX order book."""

    symbol: str
    last_update_id: int
    bids: list[tuple[Decimal, Decimal]]
    asks: list[tuple[Decimal, Decimal]]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "symbol",
            _required_text(self.symbol, field_name="symbol"),
        )
        object.__setattr__(
            self,
            "last_update_id",
            _integer_value(
                self.last_update_id,
                field_name="last_update_id",
                minimum=0,
            ),
        )
        object.__setattr__(
            self,
            "bids",
            _normalize_levels(
                self.bids,
                field_name="bids",
                reverse=True,
            ),
        )
        object.__setattr__(
            self,
            "asks",
            _normalize_levels(
                self.asks,
                field_name="asks",
                reverse=False,
            ),
        )

    @property
    def best_bid(self) -> Decimal:
        return self.bids[0][0] if self.bids else _ZERO

    @property
    def best_ask(self) -> Decimal:
        return self.asks[0][0] if self.asks else _ZERO

    @property
    def spread(self) -> Decimal:
        if not self.bids or not self.asks:
            return _ZERO

        return self.best_ask - self.best_bid

    @property
    def mid_price(self) -> Decimal:
        if not self.bids or not self.asks:
            return _ZERO

        return (self.best_bid + self.best_ask) / Decimal("2")


@dataclass(frozen=True, slots=True)
class BingXKline:
    """Normalized BingX candlestick."""

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

    def __post_init__(self) -> None:
        open_time = _utc_datetime(
            self.open_time,
            field_name="open_time",
        )
        close_time = _utc_datetime(
            self.close_time,
            field_name="close_time",
        )

        assert open_time is not None
        assert close_time is not None

        if close_time < open_time:
            raise ValueError(
                "close_time cannot be earlier than open_time."
            )

        object.__setattr__(self, "open_time", open_time)
        object.__setattr__(self, "close_time", close_time)

        for field_name in ("open", "high", "low", "close"):
            object.__setattr__(
                self,
                field_name,
                _decimal_value(
                    getattr(self, field_name),
                    field_name=field_name,
                    minimum=_ZERO,
                ),
            )

        if self.high < max(self.open, self.close, self.low):
            raise ValueError(
                "high must be greater than or equal to all OHLC prices."
            )

        if self.low > min(self.open, self.close, self.high):
            raise ValueError(
                "low must be less than or equal to all OHLC prices."
            )

        for field_name in (
            "volume",
            "quote_volume",
            "taker_buy_volume",
            "taker_buy_quote_volume",
        ):
            object.__setattr__(
                self,
                field_name,
                _decimal_value(
                    getattr(self, field_name),
                    field_name=field_name,
                    minimum=_ZERO,
                ),
            )

        object.__setattr__(
            self,
            "trades_count",
            _integer_value(
                self.trades_count,
                field_name="trades_count",
                minimum=0,
            ),
        )


@dataclass(frozen=True, slots=True)
class BingXFundingRate:
    """Normalized BingX funding-rate snapshot."""

    symbol: str
    funding_rate: Decimal
    funding_time: datetime
    mark_price: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "symbol",
            _required_text(self.symbol, field_name="symbol"),
        )
        object.__setattr__(
            self,
            "funding_rate",
            _decimal_value(
                self.funding_rate,
                field_name="funding_rate",
            ),
        )
        funding_time = _utc_datetime(
            self.funding_time,
            field_name="funding_time",
        )
        assert funding_time is not None
        object.__setattr__(self, "funding_time", funding_time)
        object.__setattr__(
            self,
            "mark_price",
            _decimal_value(
                self.mark_price,
                field_name="mark_price",
                minimum=_ZERO,
            ),
        )


@dataclass(frozen=True, slots=True)
class BingXTrade:
    """Normalized BingX public trade."""

    trade_id: int
    price: Decimal
    quantity: Decimal
    side: BingXOrderSide
    timestamp: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "trade_id",
            _integer_value(
                self.trade_id,
                field_name="trade_id",
                minimum=0,
            ),
        )
        object.__setattr__(
            self,
            "price",
            _decimal_value(
                self.price,
                field_name="price",
                strictly_positive=True,
            ),
        )
        object.__setattr__(
            self,
            "quantity",
            _decimal_value(
                self.quantity,
                field_name="quantity",
                minimum=_ZERO,
            ),
        )
        object.__setattr__(
            self,
            "side",
            _enum_value(
                BingXOrderSide,
                self.side,
                field_name="side",
            ),
        )
        timestamp = _utc_datetime(
            self.timestamp,
            field_name="timestamp",
        )
        assert timestamp is not None
        object.__setattr__(self, "timestamp", timestamp)


__all__ = (
    "BingXBalance",
    "BingXFundingRate",
    "BingXKline",
    "BingXOrder",
    "BingXOrderBook",
    "BingXOrderSide",
    "BingXOrderStatus",
    "BingXOrderType",
    "BingXPosition",
    "BingXPositionSide",
    "BingXTicker",
    "BingXTimeInForce",
    "BingXTrade",
)