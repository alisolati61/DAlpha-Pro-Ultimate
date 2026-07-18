from src.data.data_manager import (
    DataManager,
    DataPacket,
)


def packet():

    return DataPacket(
        symbol="BTCUSDT",
        timeframe="1h",
        candles=[
            [1, 2, 3, 4],
        ],
    )


def test_insert():

    manager = DataManager()

    manager.update(packet())

    assert manager.size == 1


def test_get():

    manager = DataManager()

    manager.update(packet())

    data = manager.get(
        "BTCUSDT",
        "1h",
    )

    assert data is not None

    assert data.symbol == "BTCUSDT"


def test_missing():

    manager = DataManager()

    assert manager.get(
        "ETHUSDT",
        "1h",
    ) is None


def test_clear():

    manager = DataManager()

    manager.update(packet())

    manager.clear()

    assert manager.size == 0


def test_types():

    manager = DataManager()

    manager.update(packet())

    data = manager.get(
        "BTCUSDT",
        "1h",
    )

    assert isinstance(data, DataPacket)

    assert isinstance(data.candles, list)