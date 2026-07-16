from __future__ import annotations

from src.execution.position_manager import (
    Position,
)


class PortfolioManager:

    def __init__(self):

        self.balance: float = 0.0

        self.positions: dict[str, Position] = {}

    def set_balance(
        self,
        balance: float,
    ) -> None:

        self.balance = balance

    def get_balance(self) -> float:

        return self.balance

    def add_position(
        self,
        position: Position,
    ) -> None:

        self.positions[position.symbol] = position

    def remove_position(
        self,
        symbol: str,
    ) -> None:

        self.positions.pop(symbol, None)

    def get_position(
        self,
        symbol: str,
    ) -> Position | None:

        return self.positions.get(symbol)

    def all_positions(self):

        return list(self.positions.values())

    def total_unrealized_pnl(self) -> float:

        return sum(
            p.unrealized_pnl
            for p in self.positions.values()
        )

    def equity(self) -> float:

        return self.balance + self.total_unrealized_pnl()

    def total_exposure(self) -> float:

        return sum(
            abs(
                p.current_price * p.size
            )
            for p in self.positions.values()
        )