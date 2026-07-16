from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RiskStatus(str, Enum):
    OK = "OK"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    KILL_SWITCH = "KILL_SWITCH"


@dataclass(slots=True)
class RiskSettings:
    max_risk_per_trade: float = 0.01
    max_daily_loss: float = 0.05
    max_drawdown: float = 0.15


class RiskManager:

    def __init__(self, settings: RiskSettings | None = None):

        self.settings = settings or RiskSettings()

        self.kill_switch = False

    def calculate_risk_amount(self, balance: float) -> float:

        if balance <= 0:
            raise ValueError("Balance must be greater than zero.")

        return balance * self.settings.max_risk_per_trade

    def check_daily_loss(self, daily_loss: float) -> bool:

        return daily_loss < self.settings.max_daily_loss

    def check_drawdown(
        self,
        peak_balance: float,
        current_balance: float,
    ) -> bool:

        if peak_balance <= 0:
            return False

        drawdown = (
            peak_balance - current_balance
        ) / peak_balance

        return drawdown < self.settings.max_drawdown

    def activate_kill_switch(self) -> None:

        logger.warning("Kill Switch Activated")

        self.kill_switch = True

    def deactivate_kill_switch(self) -> None:

        logger.info("Kill Switch Deactivated")

        self.kill_switch = False

    def can_trade(
        self,
        daily_loss: float,
        peak_balance: float,
        current_balance: float,
    ) -> bool:

        if self.kill_switch:
            return False

        if not self.check_daily_loss(daily_loss):
            return False

        if not self.check_drawdown(
            peak_balance,
            current_balance,
        ):
            return False

        return True

    def status(
        self,
        daily_loss: float,
        peak_balance: float,
        current_balance: float,
    ) -> RiskStatus:

        if self.kill_switch:
            return RiskStatus.KILL_SWITCH

        if not self.check_daily_loss(daily_loss):
            return RiskStatus.DAILY_LOSS_LIMIT

        if not self.check_drawdown(
            peak_balance,
            current_balance,
        ):
            return RiskStatus.MAX_DRAWDOWN

        return RiskStatus.OK