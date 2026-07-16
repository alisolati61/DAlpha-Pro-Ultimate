from datetime import datetime

from src.shared.clock import FrozenClock

from src.shared.clock import SystemClock


def test_system_clock():

    now = SystemClock().now()

    assert isinstance(now, datetime)


def test_frozen_clock():

    fixed = datetime(2025, 1, 1)

    clock = FrozenClock(fixed)

    assert clock.now() == fixed