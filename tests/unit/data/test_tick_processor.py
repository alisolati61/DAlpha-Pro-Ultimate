from datetime import datetime

from src.data.tick_processor import TickProcessor
from src.domain.market_data import MarketData


def test_process_tick():

    processor = TickProcessor()

    tick = MarketData(
        symbol="BTCUSDT",
        price=100000,
        bid=99990,
        ask=100010,
        volume=100,
        timestamp=datetime.now(),
    )

    result = processor.process(tick)

    assert result == tick

    assert processor.last_tick == tick


def test_last_tick_initially_none():

    processor = TickProcessor()

    assert processor.last_tick is None