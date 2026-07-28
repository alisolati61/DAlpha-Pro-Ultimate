"""Tests for validated, mutation-isolated candle packet storage."""

from __future__ import annotations

from threading import Thread

import pytest

from src.data.data_manager import DataManager, DataPacket
from src.data.errors import InvalidDataPacketError


def candle(extra: object = "exchange-field") -> list[object]:
    return [1, 100, 110, 90, 105, 10, extra]


def packet(
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
) -> DataPacket:
    return DataPacket(symbol, timeframe, [candle()])


def test_valid_packet_and_atomic_replacement() -> None:
    manager = DataManager()
    first = manager.update(packet())
    second = manager.update(
        DataPacket("BTCUSDT", "1h", [candle("new")])
    )

    assert first.candles[0][6] == "exchange-field"
    assert second.candles[0][6] == "new"
    assert manager.size == 1


@pytest.mark.parametrize(
    ("symbol", "timeframe"),
    [("", "1h"), (" ", "1h"), ("BTCUSDT", ""), (None, "1h")],
)
def test_invalid_keys_are_rejected(
    symbol: object,
    timeframe: object,
) -> None:
    with pytest.raises(InvalidDataPacketError):
        DataPacket(
            symbol,  # type: ignore[arg-type]
            timeframe,  # type: ignore[arg-type]
            [candle()],
        )


def test_invalid_candles_are_rejected_before_storage() -> None:
    manager = DataManager()
    manager.update(packet())

    with pytest.raises(InvalidDataPacketError):
        DataPacket("ETHUSDT", "1h", [[1, 2, 3]])

    assert manager.size == 1
    assert manager.get("ETHUSDT", "1h") is None


def test_mutated_packet_cannot_bypass_update_validation() -> None:
    manager = DataManager()
    original = packet()
    manager.update(original)
    mutated = packet("ETHUSDT")
    mutated.candles[0][1] = -1

    with pytest.raises(InvalidDataPacketError):
        manager.update(mutated)

    assert manager.size == 1
    assert manager.get("ETHUSDT", "1h") is None


def test_input_and_output_mutation_cannot_alias_storage() -> None:
    candles = [candle({"source": "original"})]
    incoming = DataPacket("BTCUSDT", "1h", candles)
    manager = DataManager()
    manager.update(incoming)

    candles[0][1] = 999
    incoming.candles[0][1] = 888
    incoming.candles[0][6]["source"] = "changed"
    first = manager.get("BTCUSDT", "1h")
    assert first is not None
    first.candles[0][1] = 777
    first.candles[0][6]["source"] = "returned"

    second = manager.get("BTCUSDT", "1h")
    assert second is not None
    assert second.candles[0][1] == 100
    assert second.candles[0][6] == {"source": "original"}


def test_independent_keys_clear_and_missing() -> None:
    manager = DataManager()
    manager.update(packet())
    manager.update(packet("ETHUSDT", "5m"))

    assert manager.size == 2
    assert manager.get("MISSING", "1h") is None

    manager.clear()
    assert manager.size == 0


def test_concurrent_updates_are_safe() -> None:
    manager = DataManager()

    def worker(index: int) -> None:
        for value in range(1, 101):
            manager.update(
                DataPacket(
                    f"SYMBOL-{index}",
                    "1m",
                    [[value, 100, 110, 90, 105, value]],
                )
            )

    threads = [Thread(target=worker, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert manager.size == 8
    for index in range(8):
        stored = manager.get(f"SYMBOL-{index}", "1m")
        assert stored is not None
        assert stored.candles[0][0] == 100
