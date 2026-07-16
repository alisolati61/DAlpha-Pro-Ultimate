from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class Candle:
    timestamp: Optional[int]

    open: float

    high: float

    low: float

    close: float

    volume: float