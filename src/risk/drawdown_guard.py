from __future__ import annotations

from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DrawdownStatus:
    peak_balance: float
    current_balance: float
    drawdown: float
    allowed: bool


class DrawdownGuard:

    def __init__(self, max_drawdown: float = 0.15) -> None:
        self.max_drawdown = max_drawdown

    def calculate_drawdown(
        self,
        peak_balance: float,
        current_balance: float,
    ) -> float:

        if peak_balance <= 0:
            raise ValueError("Peak balance must be greater than zero.")

        drawdown = (peak_balance - current_balance) / peak_balance

        return max(drawdown, 0.0)

    def check(
        self,
        peak_balance: float,
        current_balance: float,
    ) -> DrawdownStatus:

        drawdown = self.calculate_drawdown(
            peak_balance,
            current_balance,
        )

        allowed = drawdown < self.max_drawdown

        if not allowed:
            logger.warning(
                "Maximum drawdown exceeded: %.2f%%",
                drawdown * 100,
            )

        return DrawdownStatus(
            peak_balance=peak_balance,
            current_balance=current_balance,
            drawdown=round(drawdown, 6),
            allowed=allowed,
        )

    def can_continue(
        self,
        peak_balance: float,
        current_balance: float,
    ) -> bool:

        return self.check(
            peak_balance,
            current_balance,
        ).allowed