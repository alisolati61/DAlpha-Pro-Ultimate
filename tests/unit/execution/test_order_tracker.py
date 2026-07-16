from datetime import UTC, datetime

from src.execution.order_tracker import (
    OrderState,
    OrderStatus,
    OrderTracker,
)


def test_add_order():

    tracker = OrderTracker()

    tracker.add(
        OrderState(
            order_id="1",
            symbol="BTCUSDT",
            quantity=1,
            price=100000,
            status=OrderStatus.CREATED,
            updated_at=datetime.now(UTC),
        )
    )

    assert tracker.exists("1")


def test_update_order():

    tracker = OrderTracker()

    tracker.add(
        OrderState(
            order_id="1",
            symbol="BTCUSDT",
            quantity=1,
            price=100000,
            status=OrderStatus.CREATED,
            updated_at=datetime.now(UTC),
        )
    )

    tracker.update_status(
        "1",
        OrderStatus.FILLED,
    )

    assert tracker.get("1").status == OrderStatus.FILLED