from datetime import datetime

from .clock import Clock


class FrozenClock(Clock):

    def __init__(self, value: datetime):

        self._value = value

    def now(self) -> datetime:

        return self._value