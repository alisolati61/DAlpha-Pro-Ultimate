"""Validated rolling walk-forward window generation.

The generator converts fractional train, test, and step sizes into integer
index ranges derived from the complete dataset length. Only full train/test
windows are returned; partial trailing windows are intentionally discarded.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import floor, isfinite
from numbers import Real
from typing import Sequence


@dataclass(frozen=True, slots=True)
class WalkForwardWindow:
    """Immutable half-open index ranges for one walk-forward iteration."""

    train_start: int
    train_end: int
    test_start: int
    test_end: int

    def __post_init__(self) -> None:
        for name in (
            "train_start",
            "train_end",
            "test_start",
            "test_end",
        ):
            value = getattr(self, name)

            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")

            if value < 0:
                raise ValueError(
                    f"{name} must be greater than or equal to zero"
                )

        if self.train_start >= self.train_end:
            raise ValueError(
                "train_start must be less than train_end"
            )

        if self.train_end != self.test_start:
            raise ValueError(
                "train_end must equal test_start"
            )

        if self.test_start >= self.test_end:
            raise ValueError(
                "test_start must be less than test_end"
            )

    @property
    def train_length(self) -> int:
        """Return the number of observations in the training range."""

        return self.train_end - self.train_start

    @property
    def test_length(self) -> int:
        """Return the number of observations in the test range."""

        return self.test_end - self.test_start

    @property
    def total_length(self) -> int:
        """Return the combined train and test window length."""

        return self.test_end - self.train_start

    @property
    def train_slice(self) -> slice:
        """Return a slice selecting the training range."""

        return slice(
            self.train_start,
            self.train_end,
        )

    @property
    def test_slice(self) -> slice:
        """Return a slice selecting the test range."""

        return slice(
            self.test_start,
            self.test_end,
        )


class WalkForward:
    """Generate deterministic rolling train/test windows."""

    def generate(
        self,
        data: Sequence[object],
        train_size: float = 0.7,
        test_size: float = 0.2,
        step: float = 0.1,
    ) -> list[WalkForwardWindow]:
        """Return full rolling windows for a sized historical dataset.

        ``train_size``, ``test_size``, and ``step`` are fractions of the full
        dataset length and must each be in the interval ``(0.0, 1.0]``.
        Training and test fractions together may not exceed ``1.0``.

        Fractional observation counts are rounded down and then clamped to one,
        preserving the package's original behavior for very small datasets.
        """

        total = _validate_data(data)

        train_fraction = _validate_fraction(
            "train_size",
            train_size,
        )
        test_fraction = _validate_fraction(
            "test_size",
            test_size,
        )
        step_fraction = _validate_fraction(
            "step",
            step,
        )

        if train_fraction + test_fraction > 1.0:
            raise ValueError(
                "train_size and test_size must sum to at most 1.0"
            )

        if total == 0:
            return []

        train_length = max(
            1,
            floor(total * train_fraction),
        )
        test_length = max(
            1,
            floor(total * test_fraction),
        )
        stride = max(
            1,
            floor(total * step_fraction),
        )

        windows: list[WalkForwardWindow] = []
        start = 0

        while True:
            train_end = start + train_length
            test_start = train_end
            test_end = test_start + test_length

            if test_end > total:
                break

            windows.append(
                WalkForwardWindow(
                    train_start=start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                )
            )

            start += stride

        return windows


def _validate_data(
    data: object,
) -> int:
    if isinstance(
        data,
        (
            str,
            bytes,
            bytearray,
        ),
    ):
        raise TypeError(
            "data must be a sized sequence"
        )

    try:
        total = len(data)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError(
            "data must be a sized sequence"
        ) from exc

    if isinstance(total, bool) or not isinstance(total, int):
        raise TypeError(
            "data length must be an integer"
        )

    if total < 0:
        raise ValueError(
            "data length must be greater than or equal to zero"
        )

    return total


def _validate_fraction(
    name: str,
    value: object,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(
            f"{name} must be a real number"
        )

    fraction = float(value)

    if not isfinite(fraction):
        raise ValueError(
            f"{name} must be finite"
        )

    if not 0.0 < fraction <= 1.0:
        raise ValueError(
            f"{name} must be between 0.0 exclusive and 1.0 inclusive"
        )

    return fraction


__all__ = [
    "WalkForward",
    "WalkForwardWindow",
]