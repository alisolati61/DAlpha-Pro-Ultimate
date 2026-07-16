from datetime import datetime

from .clock import Clock


class SystemClock(Clock):

    def now(self) -> datetime:

        return datetime.now()