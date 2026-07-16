from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class Position:
    symbol: str
    side: str
    size: float
    entry_price: float

    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    leverage: float = 1.0

    stop_loss: float | None = None
    take_profit: float | None = None

    opened_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class PositionManager:

    def __init__(self):
        self.positions: dict[str, Position] = {}

    def open_position(
        self,
        position: Position,
    ) -> None:

        self.positions[position.symbol] = position

    def close_position(
        self,
        symbol: str,
    ) -> None:

        self.positions.pop(symbol, None)

    def get_position(
        self,
        symbol: str,
    ) -> Position | None:

        return self.positions.get(symbol)

    def list_positions(
        self,
    ) -> list[Position]:

        return list(self.positions.values())

    def update_price(
        self,
        symbol: str,
        price: float,
    ) -> None:

        position = self.positions.get(symbol)

        if position is None:
            return

        position.current_price = price

        if position.side.upper() == "BUY":

            position.unrealized_pnl = (
                price - position.entry_price
            ) * position.size

        else:

            position.unrealized_pnl = (
                position.entry_price - price
            ) * position.size

    def exists(
        self,
        symbol: str,
    ) -> bool:

        return symbol in self.positions