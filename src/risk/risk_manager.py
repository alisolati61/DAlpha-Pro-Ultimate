from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import Enum

from src.risk.drawdown_guard import DrawdownGuard
from src.risk.kill_switch import KillSwitch


logger = logging.getLogger(__name__)


class RiskStatus(str, Enum):
    OK = "OK"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    KILL_SWITCH = "KILL_SWITCH"


@dataclass(frozen=True, slots=True)
class RiskSettings:
    max_risk_per_trade: float = 0.01
    max_daily_loss: float = 0.05
    max_drawdown: float = 0.15


class RiskManager:
    """
    Central risk decision layer.

    Delegates:

    - drawdown enforcement to DrawdownGuard;
    - emergency stop state to KillSwitch;
    - daily loss and per-trade risk validation to this layer.

    All ratios use fractional notation:

        0.01 = 1%
        0.05 = 5%
        0.15 = 15%

    Boundary behavior is strict:

        daily_loss == max_daily_loss
            rejected

        drawdown == max_drawdown
            rejected
    """

    def __init__(
        self,
        settings: RiskSettings | None = None,
        drawdown_guard: DrawdownGuard | None = None,
        kill_switch: KillSwitch | None = None,
    ) -> None:

        self.settings = (
            settings
            if settings is not None
            else RiskSettings()
        )

        self._validate_settings(
            self.settings
        )

        self.drawdown_guard = (
            drawdown_guard
            if drawdown_guard is not None
            else DrawdownGuard(
                max_drawdown=(
                    self.settings.max_drawdown
                )
            )
        )

        self.kill_switch = (
            kill_switch
            if kill_switch is not None
            else KillSwitch()
        )

    # --------------------------------------------------

    @staticmethod
    def _validate_ratio(
        value: float,
        name: str,
        *,
        allow_zero: bool = True,
    ) -> None:

        if not isinstance(
            value,
            (int, float),
        ):

            raise TypeError(
                f"{name} must be a number."
            )

        if not math.isfinite(value):

            raise ValueError(
                f"{name} must be finite."
            )

        minimum = 0 if allow_zero else 0

        if value < minimum or value > 1:

            raise ValueError(
                f"{name} must be between 0 and 1."
            )

    # --------------------------------------------------

    @classmethod
    def _validate_settings(
        cls,
        settings: RiskSettings,
    ) -> None:

        if not isinstance(
            settings,
            RiskSettings,
        ):

            raise TypeError(
                "settings must be a RiskSettings."
            )

        cls._validate_ratio(
            settings.max_risk_per_trade,
            "max_risk_per_trade",
        )

        cls._validate_ratio(
            settings.max_daily_loss,
            "max_daily_loss",
        )

        cls._validate_ratio(
            settings.max_drawdown,
            "max_drawdown",
        )

        if settings.max_risk_per_trade == 0:

            raise ValueError(
                "max_risk_per_trade must be greater than zero."
            )

        if settings.max_daily_loss == 0:

            raise ValueError(
                "max_daily_loss must be greater than zero."
            )

        if settings.max_drawdown == 0:

            raise ValueError(
                "max_drawdown must be greater than zero."
            )

    # --------------------------------------------------

    @staticmethod
    def _validate_finite(
        value: float,
        name: str,
    ) -> None:

        if not isinstance(
            value,
            (int, float),
        ):

            raise TypeError(
                f"{name} must be a number."
            )

        if not math.isfinite(value):

            raise ValueError(
                f"{name} must be finite."
            )

    # --------------------------------------------------

    def calculate_risk_amount(
        self,
        balance: float,
    ) -> float:

        self._validate_finite(
            balance,
            "balance",
        )

        if balance <= 0:

            raise ValueError(
                "Balance must be greater than zero."
            )

        return float(
            balance
            * self.settings.max_risk_per_trade
        )

    # --------------------------------------------------

    def check_daily_loss(
        self,
        daily_loss: float,
    ) -> bool:

        self._validate_finite(
            daily_loss,
            "daily_loss",
        )

        if daily_loss < 0:

            raise ValueError(
                "Daily loss cannot be negative."
            )

        return (
            daily_loss
            < self.settings.max_daily_loss
        )

    # --------------------------------------------------

    def check_drawdown(
        self,
        peak_balance: float,
        current_balance: float,
    ) -> bool:

        try:

            return self.drawdown_guard.can_continue(
                peak_balance,
                current_balance,
            )

        except (
            TypeError,
            ValueError,
        ):

            return False

    # --------------------------------------------------

    def activate_kill_switch(
        self,
        reason: str = "Risk manager activation",
    ) -> None:

        logger.warning(
            "Kill Switch Activated: %s",
            reason,
        )

        self.kill_switch.activate(
            reason
        )

    # --------------------------------------------------

    def deactivate_kill_switch(
        self,
    ) -> None:

        logger.info(
            "Kill Switch Deactivated"
        )

        self.kill_switch.deactivate()

    # --------------------------------------------------

    def can_trade(
        self,
        daily_loss: float,
        peak_balance: float,
        current_balance: float,
    ) -> bool:

        return (
            self.status(
                daily_loss,
                peak_balance,
                current_balance,
            )
            == RiskStatus.OK
        )

    # --------------------------------------------------

    def status(
        self,
        daily_loss: float,
        peak_balance: float,
        current_balance: float,
    ) -> RiskStatus:

        if self.kill_switch.active:

            return RiskStatus.KILL_SWITCH

        if not self.check_daily_loss(
            daily_loss
        ):

            return RiskStatus.DAILY_LOSS_LIMIT

        if not self.check_drawdown(
            peak_balance,
            current_balance,
        ):

            return RiskStatus.MAX_DRAWDOWN

        return RiskStatus.OK