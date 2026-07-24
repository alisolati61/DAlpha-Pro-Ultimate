"""Deterministic generic pre-trade validation.

This module validates position-level constraints that do not require knowledge
of trade direction:

- position size;
- leverage;
- entry price;
- stop-loss price;
- entry and stop-loss inequality.

Direction-specific rules, exchange filters, margin calculations, and portfolio
limits belong to higher-level risk and order-normalization layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real

_MAX_REASON_LENGTH = 500


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Immutable result of a pre-trade validation."""

    approved: bool
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.approved, bool):
            raise TypeError(
                "approved must be a bool"
            )

        if self.reason is not None and not isinstance(
            self.reason,
            str,
        ):
            raise TypeError(
                "reason must be a string or None"
            )

        reason = (
            None
            if self.reason is None
            else self.reason.strip()
        )

        if self.approved:
            if reason is not None:
                raise ValueError(
                    "approved result must not have a reason"
                )
        else:
            if not reason:
                raise ValueError(
                    "rejected result requires a reason"
                )

            if len(reason) > _MAX_REASON_LENGTH:
                raise ValueError(
                    "reason must not exceed "
                    f"{_MAX_REASON_LENGTH} characters"
                )

        object.__setattr__(
            self,
            "reason",
            reason,
        )

    @classmethod
    def approve(cls) -> ValidationResult:
        """Create an approved result."""

        return cls(
            approved=True,
            reason=None,
        )

    @classmethod
    def reject(
        cls,
        reason: str,
    ) -> ValidationResult:
        """Create a rejected result with a normalized reason."""

        return cls(
            approved=False,
            reason=reason,
        )

    @property
    def rejected(self) -> bool:
        """Return whether validation failed."""

        return not self.approved


class PreTradeValidator:
    """Validate generic position-level limits before order execution."""

    INVALID_POSITION_SIZE_REASON = (
        "Position size must be a finite number "
        "greater than zero."
    )
    POSITION_SIZE_LIMIT_REASON = (
        "Position size exceeds maximum allowed."
    )
    INVALID_LEVERAGE_REASON = (
        "Leverage must be a finite number "
        "greater than zero."
    )
    LEVERAGE_LIMIT_REASON = (
        "Leverage exceeds maximum allowed."
    )
    INVALID_ENTRY_PRICE_REASON = (
        "Entry price must be a finite number "
        "greater than zero."
    )
    INVALID_STOP_LOSS_REASON = (
        "Stop loss must be a finite number "
        "greater than zero."
    )
    EQUAL_STOP_REASON = (
        "Stop loss cannot equal entry price."
    )

    __slots__ = (
        "max_leverage",
        "max_position_size",
    )

    def __init__(
        self,
        max_position_size: float,
        max_leverage: float,
    ) -> None:
        self.max_position_size = (
            _validate_positive_finite_configuration(
                max_position_size,
                "max_position_size",
            )
        )
        self.max_leverage = (
            _validate_positive_finite_configuration(
                max_leverage,
                "max_leverage",
            )
        )

    def validate_position_size(
        self,
        position_size: float,
    ) -> ValidationResult:
        """Validate positive finite size against the configured ceiling."""

        size = _coerce_positive_finite(
            position_size,
        )

        if size is None:
            return ValidationResult.reject(
                self.INVALID_POSITION_SIZE_REASON
            )

        if size > self.max_position_size:
            return ValidationResult.reject(
                self.POSITION_SIZE_LIMIT_REASON
            )

        return ValidationResult.approve()

    def validate_leverage(
        self,
        leverage: float,
    ) -> ValidationResult:
        """Validate positive finite leverage against the configured ceiling."""

        normalized_leverage = _coerce_positive_finite(
            leverage,
        )

        if normalized_leverage is None:
            return ValidationResult.reject(
                self.INVALID_LEVERAGE_REASON
            )

        if normalized_leverage > self.max_leverage:
            return ValidationResult.reject(
                self.LEVERAGE_LIMIT_REASON
            )

        return ValidationResult.approve()

    def validate_entry_price(
        self,
        entry_price: float,
    ) -> ValidationResult:
        """Validate that entry price is positive and finite."""

        if _coerce_positive_finite(
            entry_price,
        ) is None:
            return ValidationResult.reject(
                self.INVALID_ENTRY_PRICE_REASON
            )

        return ValidationResult.approve()

    def validate_stop_loss_price(
        self,
        stop_loss: float,
    ) -> ValidationResult:
        """Validate that stop-loss price is positive and finite."""

        if _coerce_positive_finite(
            stop_loss,
        ) is None:
            return ValidationResult.reject(
                self.INVALID_STOP_LOSS_REASON
            )

        return ValidationResult.approve()

    def validate_stop_loss(
        self,
        entry_price: float,
        stop_loss: float,
    ) -> ValidationResult:
        """Validate entry, stop loss, and their inequality."""

        result = self.validate_entry_price(
            entry_price,
        )

        if not result.approved:
            return result

        result = self.validate_stop_loss_price(
            stop_loss,
        )

        if not result.approved:
            return result

        if float(entry_price) == float(stop_loss):
            return ValidationResult.reject(
                self.EQUAL_STOP_REASON
            )

        return ValidationResult.approve()

    def validate(
        self,
        position_size: float,
        leverage: float,
        entry_price: float,
        stop_loss: float,
    ) -> ValidationResult:
        """Validate a trade in deterministic first-failure order."""

        validations = (
            self.validate_position_size(
                position_size,
            ),
            self.validate_leverage(
                leverage,
            ),
            self.validate_stop_loss(
                entry_price,
                stop_loss,
            ),
        )

        for result in validations:
            if not result.approved:
                return result

        return ValidationResult.approve()

    def validate_all(
        self,
        position_size: float,
        leverage: float,
        entry_price: float,
        stop_loss: float,
    ) -> tuple[ValidationResult, ...]:
        """Return every failed validation in deterministic order.

        A fully valid trade returns a one-item tuple containing an approved
        result. This method is diagnostic; execution paths should normally use
        :meth:`validate`.
        """

        results = (
            self.validate_position_size(
                position_size,
            ),
            self.validate_leverage(
                leverage,
            ),
            self.validate_stop_loss(
                entry_price,
                stop_loss,
            ),
        )

        failures = tuple(
            result
            for result in results
            if not result.approved
        )

        if failures:
            return failures

        return (
            ValidationResult.approve(),
        )

    def position_size_utilization(
        self,
        position_size: float,
    ) -> float:
        """Return size as a fraction of the configured maximum.

        Unlike validation methods, this diagnostic helper raises for invalid
        input rather than converting it into a rejection result.
        """

        size = _require_positive_finite_runtime(
            position_size,
            "position_size",
        )

        return float(
            size
            / self.max_position_size
        )

    def leverage_utilization(
        self,
        leverage: float,
    ) -> float:
        """Return leverage as a fraction of the configured maximum."""

        normalized_leverage = (
            _require_positive_finite_runtime(
                leverage,
                "leverage",
            )
        )

        return float(
            normalized_leverage
            / self.max_leverage
        )


def _validate_positive_finite_configuration(
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

    if number <= 0.0:
        raise ValueError(
            f"{name} must be greater than zero."
        )

    return number


def _coerce_positive_finite(
    value: object,
) -> float | None:
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
    ):
        return None

    number = float(value)

    if (
        not isfinite(number)
        or number <= 0.0
    ):
        return None

    return number


def _require_positive_finite_runtime(
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

    if number <= 0.0:
        raise ValueError(
            f"{name} must be greater than zero."
        )

    return number


__all__ = (
    "PreTradeValidator",
    "ValidationResult",
)