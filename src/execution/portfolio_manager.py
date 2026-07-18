from __future__ import annotations

import math

from src.execution.position_manager import Position


class PortfolioManager:
    """
    Manages account balance and open execution positions.

    Responsibilities:
    - Store account balance.
    - Track open positions by symbol.
    - Calculate unrealized PnL.
    - Calculate equity.
    - Calculate current gross exposure.
    """

    def __init__(
        self,
        balance: float = 0.0,
    ) -> None:

        self.balance = self._validate_balance(
            balance,
        )

        self.positions: dict[str, Position] = {}

    @staticmethod
    def _validate_balance(
        balance: float,
    ) -> float:

        if isinstance(
            balance,
            bool,
        ):

            raise TypeError(
                "balance must be a number."
            )

        if not isinstance(
            balance,
            (int, float),
        ):

            raise TypeError(
                "balance must be a number."
            )

        balance = float(balance)

        if not math.isfinite(
            balance,
        ):

            raise ValueError(
                "balance must be finite."
            )

        if balance < 0:

            raise ValueError(
                "balance cannot be negative."
            )

        return balance

    @staticmethod
    def _validate_symbol(
        symbol: str,
    ) -> str:

        if not isinstance(
            symbol,
            str,
        ):

            raise TypeError(
                "symbol must be a string."
            )

        symbol = symbol.strip()

        if not symbol:

            raise ValueError(
                "symbol cannot be empty."
            )

        return symbol

    def set_balance(
        self,
        balance: float,
    ) -> None:

        self.balance = self._validate_balance(
            balance,
        )

    def get_balance(
        self,
    ) -> float:

        return self.balance

    def add_position(
        self,
        position: Position,
    ) -> None:

        if not isinstance(
            position,
            Position,
        ):

            raise TypeError(
                "position must be a Position."
            )

        symbol = self._validate_symbol(
            position.symbol,
        )

        position.symbol = symbol

        self.positions[symbol] = position

    def remove_position(
        self,
        symbol: str,
    ) -> None:

        symbol = self._validate_symbol(
            symbol,
        )

        self.positions.pop(
            symbol,
            None,
        )

    def get_position(
        self,
        symbol: str,
    ) -> Position | None:

        symbol = self._validate_symbol(
            symbol,
        )

        return self.positions.get(
            symbol,
        )

    def all_positions(
        self,
    ) -> list[Position]:

        return list(
            self.positions.values(),
        )

    def total_unrealized_pnl(
        self,
    ) -> float:

        return float(
            sum(
                position.unrealized_pnl
                for position in self.positions.values()
            ),
        )

    def equity(
        self,
    ) -> float:

        return float(
            self.balance
            + self.total_unrealized_pnl(),
        )

    def total_exposure(
        self,
    ) -> float:

        return float(
            sum(
                abs(
                    position.current_price
                    * position.size
                )
                for position in self.positions.values()
            ),
        )