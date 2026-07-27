"""Behavioral tests for validated BingX transport models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.exchange.models import (
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
    BingXTrade,
)


def test_balance_normalizes_asset_and_numeric_values() -> None:
    balance = BingXBalance(
        asset=" usdt ",
        wallet_balance="100.5",
        unrealized_pnl="-2.5",
        margin_balance=98,
        available_balance="80",
        max_withdraw_amount=75,
    )

    assert balance.asset == "USDT"
    assert balance.wallet_balance == Decimal("100.5")
    assert balance.total_equity == Decimal("98.0")


def test_models_are_immutable_boundary_values() -> None:
    balance = BingXBalance(
        "USDT",
        1,
        0,
        1,
        1,
        1,
    )

    with pytest.raises(FrozenInstanceError):
        balance.asset = "BTC"  # type: ignore[misc]


def test_position_converts_enums_and_calculates_long_pnl() -> None:
    position = BingXPosition(
        symbol="BTC-USDT",
        position_side="long",
        position_amount="2",
        entry_price="100",
        mark_price="110",
        unrealized_pnl="20",
        liquidation_price="50",
        leverage="10",
        margin_type="isolated",
        isolated_margin="20",
    )

    assert position.position_side is BingXPositionSide.LONG
    assert position.margin_type == "ISOLATED"
    assert position.leverage == 10
    assert position.pnl_percent == Decimal("10.00")


def test_short_position_pnl_direction_is_correct() -> None:
    position = BingXPosition(
        symbol="BTC-USDT",
        position_side="SHORT",
        position_amount="2",
        entry_price="100",
        mark_price="90",
        unrealized_pnl="20",
        liquidation_price="150",
        leverage=5,
        margin_type="crossed",
    )

    assert position.pnl_percent == Decimal("10.00")


def test_both_position_uses_negative_amount_as_short() -> None:
    position = BingXPosition(
        symbol="BTC-USDT",
        position_side="BOTH",
        position_amount="-1",
        entry_price="100",
        mark_price="90",
        unrealized_pnl="10",
        liquidation_price="150",
        leverage=5,
        margin_type="crossed",
    )

    assert position.pnl_percent == Decimal("10.00")


def test_zero_entry_price_has_zero_pnl_percent() -> None:
    position = BingXPosition(
        symbol="BTC-USDT",
        position_side="LONG",
        position_amount="0",
        entry_price="0",
        mark_price="0",
        unrealized_pnl="0",
        liquidation_price="0",
        leverage=1,
        margin_type="crossed",
    )

    assert position.pnl_percent == Decimal("0")


def test_order_normalizes_strings_enums_decimals_and_timestamps() -> None:
    order = BingXOrder(
        order_id=" 123 ",
        symbol="BTC-USDT",
        side="buy",
        position_side="long",
        order_type="limit",
        status="partially_filled",
        price="100.25",
        quantity="2",
        executed_qty="1",
        avg_price="100",
        created_at=1_700_000_000_000,
        updated_at=datetime(2023, 1, 1),
    )

    assert order.order_id == "123"
    assert order.side is BingXOrderSide.BUY
    assert order.position_side is BingXPositionSide.LONG
    assert order.order_type is BingXOrderType.LIMIT
    assert order.status is BingXOrderStatus.PARTIALLY_FILLED
    assert order.created_at is not None
    assert order.created_at.tzinfo is UTC
    assert order.updated_at == datetime(
        2023,
        1,
        1,
        tzinfo=UTC,
    )


def test_ticker_accepts_signed_change_and_normalizes_times() -> None:
    ticker = BingXTicker(
        symbol="BTC-USDT",
        last_price="100",
        price_change="-5",
        price_change_percent="-4.76",
        high_price="110",
        low_price="90",
        volume="20",
        quote_volume="2000",
        bid_price="99",
        ask_price="101",
        open_time=1_700_000_000,
        close_time=1_700_086_400,
    )

    assert ticker.price_change == Decimal("-5")
    assert ticker.open_time is not None
    assert ticker.open_time.tzinfo is UTC


def test_orderbook_sorts_levels_and_calculates_market_metrics() -> None:
    book = BingXOrderBook(
        symbol="BTC-USDT",
        last_update_id="42",
        bids=[("99", "2"), ("100", "1")],
        asks=[("102", "3"), ("101", "1")],
    )

    assert book.last_update_id == 42
    assert book.bids == [
        (Decimal("100"), Decimal("1")),
        (Decimal("99"), Decimal("2")),
    ]
    assert book.asks == [
        (Decimal("101"), Decimal("1")),
        (Decimal("102"), Decimal("3")),
    ]
    assert book.best_bid == Decimal("100")
    assert book.best_ask == Decimal("101")
    assert book.spread == Decimal("1")
    assert book.mid_price == Decimal("100.5")


def test_empty_orderbook_has_neutral_metrics() -> None:
    book = BingXOrderBook(
        symbol="BTC-USDT",
        last_update_id=0,
        bids=[],
        asks=[],
    )

    assert book.best_bid == Decimal("0")
    assert book.best_ask == Decimal("0")
    assert book.spread == Decimal("0")
    assert book.mid_price == Decimal("0")


def test_kline_normalizes_values_and_utc_datetimes() -> None:
    kline = BingXKline(
        open_time=datetime(2024, 1, 1),
        open="100",
        high="110",
        low="90",
        close="105",
        volume="10",
        close_time=datetime(2024, 1, 1, 0, 1),
        quote_volume="1000",
        trades_count="12",
        taker_buy_volume="6",
        taker_buy_quote_volume="600",
    )

    assert kline.open_time.tzinfo is UTC
    assert kline.close_time.tzinfo is UTC
    assert kline.trades_count == 12


def test_kline_rejects_invalid_ohlc_relationships() -> None:
    with pytest.raises(ValueError, match="high must be"):
        BingXKline(
            open_time=datetime(2024, 1, 1, tzinfo=UTC),
            open="100",
            high="99",
            low="90",
            close="98",
            volume="1",
            close_time=datetime(
                2024,
                1,
                1,
                0,
                1,
                tzinfo=UTC,
            ),
            quote_volume="100",
            trades_count=1,
            taker_buy_volume="0.5",
            taker_buy_quote_volume="50",
        )


def test_kline_rejects_reverse_time_window() -> None:
    open_time = datetime(2024, 1, 1, tzinfo=UTC)

    with pytest.raises(ValueError, match="close_time"):
        BingXKline(
            open_time=open_time,
            open="100",
            high="110",
            low="90",
            close="105",
            volume="1",
            close_time=open_time - timedelta(seconds=1),
            quote_volume="100",
            trades_count=1,
            taker_buy_volume="0.5",
            taker_buy_quote_volume="50",
        )


def test_funding_rate_allows_negative_rate() -> None:
    funding = BingXFundingRate(
        symbol="BTC-USDT",
        funding_rate="-0.0001",
        funding_time=1_700_000_000_000,
        mark_price="100",
    )

    assert funding.funding_rate == Decimal("-0.0001")
    assert funding.funding_time.tzinfo is UTC


def test_trade_normalizes_side_id_and_timestamp() -> None:
    trade = BingXTrade(
        trade_id="7",
        price="100.5",
        quantity="0.25",
        side="sell",
        timestamp=1_700_000_000_000,
    )

    assert trade.trade_id == 7
    assert trade.side is BingXOrderSide.SELL
    assert trade.timestamp.tzinfo is UTC


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (
            lambda: BingXBalance(
                "",
                1,
                0,
                1,
                1,
                1,
            ),
            "asset cannot be empty",
        ),
        (
            lambda: BingXPosition(
                "BTC-USDT",
                "INVALID",
                1,
                100,
                100,
                0,
                0,
                1,
                "crossed",
            ),
            "Unsupported position_side",
        ),
        (
            lambda: BingXPosition(
                "BTC-USDT",
                "LONG",
                1,
                100,
                100,
                0,
                0,
                0,
                "crossed",
            ),
            "leverage must be greater",
        ),
        (
            lambda: BingXTrade(
                1,
                0,
                1,
                "BUY",
                datetime.now(UTC),
            ),
            "price must be greater than zero",
        ),
        (
            lambda: BingXBalance(
                "USDT",
                float("nan"),
                0,
                1,
                1,
                1,
            ),
            "wallet_balance must be finite",
        ),
    ],
)
def test_invalid_model_values_are_rejected(
    factory: object,
    message: str,
) -> None:
    with pytest.raises(
        (TypeError, ValueError),
        match=message,
    ):
        factory()  # type: ignore[operator]


def test_orderbook_rejects_malformed_levels() -> None:
    with pytest.raises(TypeError, match=r"bids\[0\]"):
        BingXOrderBook(
            symbol="BTC-USDT",
            last_update_id=1,
            bids=[("100",)],  # type: ignore[list-item]
            asks=[],
        )