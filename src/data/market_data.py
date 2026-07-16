from dataclasses import dataclass
from datetime import datetime


@dataclass
class MarketData:
    symbol: str
    price: float
    bid: float
    ask: float
    volume: float
    timestamp: datetime