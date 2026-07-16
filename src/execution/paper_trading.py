from dataclasses import dataclass
from datetime import datetime


@dataclass
class PaperTrade:

    symbol: str
    side: str
    quantity: float
    entry_price: float
    timestamp: datetime


class PaperTradingEngine:

    def __init__(self):
        self.trades = []

    def execute(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ):

        trade = PaperTrade(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=price,
            timestamp=datetime.now(),
        )

        self.trades.append(trade)

        return trade

    def history(self):
        return self.trades