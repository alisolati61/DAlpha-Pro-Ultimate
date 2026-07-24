"""Central account-level risk decisions.

Ratios use fractional notation:

- ``0.01`` means 1%;
- ``0.05`` means 5%;
- ``0.15`` means 15%.

Decision priority is deterministic:

1. Kill switch
2. Daily-loss limit
3. Maximum drawdown
4. Approved
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from numbers import Real

from src.risk.drawdown_guard import DrawdownGuard
from src.risk.kill_switch import KillSwitch

logger = logging.getLogger(__name__)

_MAX_REASON_LENGTH = 500


class RiskStatus(str, Enum):
    """Account-level risk state."""

    OK = "OK"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    KILL_SWITCH = "KILL_SWITCH"


@dataclass(frozen=True, slots=True)
class RiskSettings:
    """Immutable validated risk configuration."""

    max_risk_per_trade: float = 0.01
    max_daily_loss: float = 0.05
    max_drawdown: float = 0.15

    def __post_init__(self) -> None:
        for field_name in (
            "max_risk_per_trade",
            "max_daily_loss",
            "max_drawdown",
        ):
            object.__setattr__(
                self,
                field_name,
                _validate_ratio(
                    getattr(self, field_name),
                    field_name,
                ),
            )


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Immutable detailed account-level risk decision."""

    allowed: bool
    status: RiskStatus
    reason: str = ""
    daily_loss: float | None = None
    drawdown: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool):
            raise TypeError("allowed must be a bool")

        if not isinstance(self.status, RiskStatus):
            raise TypeError("status must be a RiskStatus")

        if not isinstance(self.reason, str):
            raise TypeError("reason must be a string")

        reason = self.reason.strip()

        if len(reason) > _MAX_REASON_LENGTH:
            raise ValueError(
                "reason must not exceed 500 characters"
            )

        if self.status is RiskStatus.OK:
            if not self.allowed:
                raise ValueError(
                    "OK assessment must be allowed"
                )
            if reason:
                raise ValueError(
                    "OK assessment must not have a reason"
                )
        else:
            if self.allowed:
                raise ValueError(
                    "blocking assessment cannot be allowed"
                )
            if not reason:
                raise ValueError(
                    "blocking assessment requires a reason"
                )

        daily_loss = self.daily_loss
        if daily_loss is not None:
            daily_loss = _validate_non_negative_finite(
                daily_loss,
                "daily_loss",
            )

        drawdown = self.drawdown
        if drawdown is not None:
            drawdown = _validate_unit_interval(
                drawdown,
                "drawdown",
            )

        object.__setattr__(self, "reason", reason)
        object.__setattr__(
            self,
            "daily_loss",
            daily_loss,
        )
        object.__setattr__(
            self,
            "drawdown",
            drawdown,
        )

    @property
    def blocked(self) -> bool:
        """Return whether trading is blocked."""

        return not self.allowed


class RiskManager:
    """Central account-level risk decision layer."""

    KILL_SWITCH_FALLBACK_REASON = (
        "Kill switch is active."
    )
    DAILY_LOSS_REASON = (
        "Daily loss limit reached or exceeded."
    )
    MAX_DRAWDOWN_REASON = (
        "Maximum drawdown reached or exceeded."
    )
    INVALID_DRAWDOWN_REASON = (
        "Drawdown inputs are invalid."
    )

    __slots__ = (
        "drawdown_guard",
        "kill_switch",
        "settings",
    )

    def __init__(
        self,
        settings: RiskSettings | None = None,
        drawdown_guard: DrawdownGuard | None = None,
        kill_switch: KillSwitch | None = None,
    ) -> None:
        if settings is None:
            normalized_settings = RiskSettings()
        else:
            self._validate_settings(settings)
            normalized_settings = settings

        if (
            drawdown_guard is not None
            and not isinstance(
                drawdown_guard,
                DrawdownGuard,
            )
        ):
            raise TypeError(
                "drawdown_guard must be a DrawdownGuard."
            )

        if (
            kill_switch is not None
            and not isinstance(
                kill_switch,
                KillSwitch,
            )
        ):
            raise TypeError(
                "kill_switch must be a KillSwitch."
            )

        self.settings = normalized_settings
        self.drawdown_guard = (
            drawdown_guard
            if drawdown_guard is not None
            else DrawdownGuard(
                max_drawdown=(
                    normalized_settings.max_drawdown
                )
            )
        )
        self.kill_switch = (
            kill_switch
            if kill_switch is not None
            else KillSwitch()
        )

    @staticmethod
    def _validate_settings(
        settings: RiskSettings,
    ) -> None:
        if not isinstance(settings, RiskSettings):
            raise TypeError(
                "settings must be a RiskSettings."
            )

        _validate_ratio(
            settings.max_risk_per_trade,
            "max_risk_per_trade",
        )
        _validate_ratio(
            settings.max_daily_loss,
            "max_daily_loss",
        )
        _validate_ratio(
            settings.max_drawdown,
            "max_drawdown",
        )

    def calculate_risk_amount(
        self,
        balance: float,
    ) -> float:
        """Return the maximum monetary risk for one trade."""

        normalized_balance = _validate_positive_finite(
            balance,
            "balance",
        )

        risk_amount = (
            normalized_balance
            * self.settings.max_risk_per_trade
        )

        if not isfinite(risk_amount):
            raise ValueError(
                "Risk amount calculation must be finite."
            )

        return float(risk_amount)

    def check_daily_loss(
        self,
        daily_loss: float,
    ) -> bool:
        """Return whether daily loss remains below its hard ceiling."""

        normalized = _validate_non_negative_finite(
            daily_loss,
            "daily_loss",
        )

        return bool(
            normalized
            < self.settings.max_daily_loss
        )

    def remaining_daily_loss(
        self,
        daily_loss: float,
    ) -> float:
        """Return remaining daily-loss capacity, clamped to zero."""

        normalized = _validate_non_negative_finite(
            daily_loss,
            "daily_loss",
        )

        return float(
            max(
                self.settings.max_daily_loss
                - normalized,
                0.0,
            )
        )

    def check_drawdown(
        self,
        peak_balance: float,
        current_balance: float,
    ) -> bool:
        """Return whether drawdown is valid and below its limit.

        Invalid balance inputs fail closed and return ``False``.
        """

        try:
            return bool(
                self.drawdown_guard.can_continue(
                    peak_balance,
                    current_balance,
                )
            )
        except (TypeError, ValueError):
            return False

    def activate_kill_switch(
        self,
        reason: str = "Risk manager activation",
    ) -> None:
        """Activate the shared kill switch."""

        self.kill_switch.activate(reason)
        logger.warning(
            "Kill Switch Activated: %s",
            self.kill_switch.reason,
        )

    def deactivate_kill_switch(self) -> None:
        """Explicitly deactivate the shared kill switch."""

        self.kill_switch.deactivate()
        logger.info("Kill Switch Deactivated")

    def evaluate(
        self,
        daily_loss: float,
        peak_balance: float | None = None,
        current_balance: float | None = None,
    ) -> RiskAssessment:
        """Return a detailed account-level decision."""

        if self.kill_switch.active:
            return RiskAssessment(
                allowed=False,
                status=RiskStatus.KILL_SWITCH,
                reason=(
                    self.kill_switch.reason
                    or self.KILL_SWITCH_FALLBACK_REASON
                ),
            )

        normalized_daily_loss = (
            _validate_non_negative_finite(
                daily_loss,
                "daily_loss",
            )
        )

        if (
            normalized_daily_loss
            >= self.settings.max_daily_loss
        ):
            return RiskAssessment(
                allowed=False,
                status=RiskStatus.DAILY_LOSS_LIMIT,
                reason=self.DAILY_LOSS_REASON,
                daily_loss=normalized_daily_loss,
            )

        if (
            peak_balance is None
            and current_balance is None
        ):
            return RiskAssessment(
                allowed=True,
                status=RiskStatus.OK,
                daily_loss=normalized_daily_loss,
            )

        if (
            peak_balance is None
            or current_balance is None
        ):
            raise ValueError(
                "peak_balance and current_balance "
                "must be provided together."
            )

        try:
            drawdown_status = (
                self.drawdown_guard.check(
                    peak_balance,
                    current_balance,
                )
            )
        except (TypeError, ValueError):
            return RiskAssessment(
                allowed=False,
                status=RiskStatus.MAX_DRAWDOWN,
                reason=self.INVALID_DRAWDOWN_REASON,
                daily_loss=normalized_daily_loss,
            )

        if not drawdown_status.allowed:
            return RiskAssessment(
                allowed=False,
                status=RiskStatus.MAX_DRAWDOWN,
                reason=self.MAX_DRAWDOWN_REASON,
                daily_loss=normalized_daily_loss,
                drawdown=drawdown_status.drawdown,
            )

        return RiskAssessment(
            allowed=True,
            status=RiskStatus.OK,
            daily_loss=normalized_daily_loss,
            drawdown=drawdown_status.drawdown,
        )

    def can_trade(
        self,
        daily_loss: float,
        peak_balance: float | None = None,
        current_balance: float | None = None,
    ) -> bool:
        """Return whether account-level risk permits trading."""

        return self.evaluate(
            daily_loss=daily_loss,
            peak_balance=peak_balance,
            current_balance=current_balance,
        ).allowed

    def status(
        self,
        daily_loss: float,
        peak_balance: float,
        current_balance: float,
    ) -> RiskStatus:
        """Return the account-level risk status."""

        return self.evaluate(
            daily_loss=daily_loss,
            peak_balance=peak_balance,
            current_balance=current_balance,
        ).status


def _validate_ratio(
    value: object,
    name: str,
) -> float:
    ratio = _validate_finite_number(
        value,
        name,
    )

    if not 0.0 < ratio <= 1.0:
        raise ValueError(
            f"{name} must be between 0 and 1."
        )

    return ratio


def _validate_unit_interval(
    value: object,
    name: str,
) -> float:
    ratio = _validate_finite_number(
        value,
        name,
    )

    if not 0.0 <= ratio <= 1.0:
        raise ValueError(
            f"{name} must be between 0 and 1."
        )

    return ratio


def _validate_positive_finite(
    value: object,
    name: str,
) -> float:
    number = _validate_finite_number(
        value,
        name,
    )

    if number <= 0.0:
        if name == "balance":
            raise ValueError(
                "Balance must be greater than zero."
            )

        raise ValueError(
            f"{name} must be greater than zero."
        )

    return number


def _validate_non_negative_finite(
    value: object,
    name: str,
) -> float:
    number = _validate_finite_number(
        value,
        name,
    )

    if number < 0.0:
        if name == "daily_loss":
            raise ValueError(
                "Daily loss cannot be negative."
            )

        raise ValueError(
            f"{name} cannot be negative."
        )

    return number


def _validate_finite_number(
    value: object,
    name: str,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
    ):
        raise TypeError(
            f"{name} must be a number."
        )

    number = float(value)

    if not isfinite(number):
        raise ValueError(
            f"{name} must be finite."
        )

    return number


__all__ = (
    "RiskAssessment",
    "RiskManager",
    "RiskSettings",
    "RiskStatus",
)