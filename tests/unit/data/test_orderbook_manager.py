"""Tests for canonical local order book state."""

from __future__ import annotations

from math import inf, nan
from threading import Thread

import pytest

from src.data.errors import InvalidOrderBookError
from src.data.orderbook_manager import OrderBook, OrderBookManager


def sample() -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    return (
        [(99, 5), (100, 2), (98, 8)],
        [(103, 6), (101, 3), (102, 4)],
    )


def test_valid_snapshot_is_normalized_sorted_and_queryable() -> None:
    manager = OrderBookManager()
    bids, asks = sample()

    result = manager.update(" BTCUSDT ", bids, asks)

    assert isinstance(result, OrderBook)
    assert result.symbol == "BTCUSDT"
    assert result.bids == [(100.0, 2.0), (99.0, 5.0), (98.0, 8.0)]
    assert result.asks == [(101.0, 3.0), (102.0, 4.0), (103.0, 6.0)]
    assert manager.best_bid("BTCUSDT") == (100.0, 2.0)
    assert manager.best_ask("BTCUSDT") == (101.0, 3.0)
    assert manager.size == 1


@pytest.mark.parametrize(
    ("bids", "asks"),
    [
        ([(100, 1), (100, 2)], [(101, 1)]),
        ([(100, 1)], [(101, 1), (101, 2)]),
        ([(102, 1)], [(101, 1)]),
    ],
)
def test_duplicate_and_crossed_books_are_rejected(
    bids: list[tuple[float, float]],
    asks: list[tuple[float, float]],
) -> None:
    with pytest.raises(InvalidOrderBookError):
        OrderBookManager().update("BTCUSDT", bids, asks)


@pytest.mark.parametrize(
    "value",
    [nan, inf, -inf, True, "bad", None],
)
def test_invalid_numeric_values_are_rejected(value: object) -> None:
    with pytest.raises(InvalidOrderBookError):
        OrderBookManager().update(
            "BTCUSDT",
            [(value, 1)],  # type: ignore[list-item]
            [(101, 1)],
        )
    with pytest.raises(InvalidOrderBookError):
        OrderBookManager().update(
            "BTCUSDT",
            [(100, value)],  # type: ignore[list-item]
            [(101, 1)],
        )


def test_price_and_quantity_policy() -> None:
    manager = OrderBookManager()

    with pytest.raises(InvalidOrderBookError):
        manager.update("BTCUSDT", [(0, 1)], [])
    with pytest.raises(InvalidOrderBookError):
        manager.update("BTCUSDT", [(100, -1)], [])

    book = manager.update("BTCUSDT", [(100, 0)], [(101, 0)])
    assert book.bids == [(100.0, 0.0)]
    assert book.asks == [(101.0, 0.0)]


@pytest.mark.parametrize("symbol", ["", " ", None, 123])
def test_invalid_symbol_is_rejected(symbol: object) -> None:
    with pytest.raises(InvalidOrderBookError):
        OrderBookManager().update(
            symbol,  # type: ignore[arg-type]
            [],
            [],
        )


def test_empty_side_policy_is_explicit() -> None:
    manager = OrderBookManager()

    assert manager.update("EMPTY", [], []).bids == []
    assert manager.update("BIDS", [(100, 1)], []).asks == []
    assert manager.update("ASKS", [], [(101, 1)]).bids == []
    assert manager.best_bid("ASKS") is None
    assert manager.best_ask("BIDS") is None


def test_input_and_output_are_defensively_copied() -> None:
    manager = OrderBookManager()
    bids, asks = sample()
    manager.update("BTCUSDT", bids, asks)

    bids.append((200, 1))
    first = manager.get("BTCUSDT")
    assert first is not None
    first.bids.append((300, 1))

    second = manager.get("BTCUSDT")
    assert second is not None
    assert second.bids[0] == (100.0, 2.0)


def test_invalid_replacement_is_atomic_and_symbols_are_independent() -> None:
    manager = OrderBookManager()
    bids, asks = sample()
    original = manager.update("BTCUSDT", bids, asks)
    manager.update("ETHUSDT", [(50, 1)], [(51, 1)])

    with pytest.raises(InvalidOrderBookError):
        manager.update("BTCUSDT", [(200, 1)], [(100, 1)])

    assert manager.get("BTCUSDT") == original
    assert manager.get("ETHUSDT") is not None
    assert manager.size == 2


def test_clear_and_missing_compatibility() -> None:
    manager = OrderBookManager()
    assert manager.get("BTCUSDT") is None
    assert manager.best_bid("BTCUSDT") is None
    manager.update("BTCUSDT", [], [])
    manager.clear()
    assert manager.size == 0


def test_concurrent_updates_preserve_independent_symbols() -> None:
    manager = OrderBookManager()

    def worker(index: int) -> None:
        for price in range(1, 101):
            manager.update(
                f"SYMBOL-{index}",
                [(price, index)],
                [(price + 1, index)],
            )

    threads = [Thread(target=worker, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert manager.size == 8
    for index in range(8):
        assert manager.best_bid(f"SYMBOL-{index}") == (
            100.0,
            float(index),
        )
