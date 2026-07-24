"""Validated execution of historical strategy signals.

Each signal is converted to a ``TradeRequest``, simulated in input order, and
returned as a ``TradePerformance`` record. The runner preserves the existing
long-trade contract used by the backtesting package.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from math import isfinite
from numbers import Real

from src.ai.performance_tracker import TradePerformance
from src.backtesting.trade_simulator import (
    TradeRequest,
    TradeSimulationResult,
    TradeSimulator,
)


@dataclass(frozen=True, slots=True)
class CandleSignal:
    """Validated historical signal consumed by ``StrategyRunner``."""

    symbol: str
    timeframe: str
    entry_price: float
    exit_price: float
    quantity: float
    strategy: str
    confidence: float
    duration_minutes: int
    risk_reward: float

    def __post_init__(self) -> None:
        symbol = _validate_non_empty_text(
            "symbol",
            self.symbol,
        )

        timeframe = _validate_non_empty_text(
            "timeframe",
            self.timeframe,
        )

        strategy = _validate_non_empty_text(
            "strategy",
            self.strategy,
        )

        entry_price = _validate_positive_number(
            "entry_price",
            self.entry_price,
        )

        exit_price = _validate_positive_number(
            "exit_price",
            self.exit_price,
        )

        quantity = _validate_non_negative_number(
            "quantity",
            self.quantity,
        )

        confidence = _validate_percentage(
            "confidence",
            self.confidence,
        )

        duration_minutes = _validate_non_negative_integer(
            "duration_minutes",
            self.duration_minutes,
        )

        risk_reward = _validate_non_negative_number(
            "risk_reward",
            self.risk_reward,
        )

        object.__setattr__(
            self,
            "symbol",
            symbol,
        )

        object.__setattr__(
            self,
            "timeframe",
            timeframe,
        )

        object.__setattr__(
            self,
            "strategy",
            strategy,
        )

        object.__setattr__(
            self,
            "entry_price",
            entry_price,
        )

        object.__setattr__(
            self,
            "exit_price",
            exit_price,
        )

        object.__setattr__(
            self,
            "quantity",
            quantity,
        )

        object.__setattr__(
            self,
            "confidence",
            confidence,
        )

        object.__setattr__(
            self,
            "duration_minutes",
            duration_minutes,
        )

        object.__setattr__(
            self,
            "risk_reward",
            risk_reward,
        )


class StrategyRunner:
    """Simulate validated historical signals in deterministic input order."""

    __slots__ = ("simulator",)

    def __init__(
        self,
        simulator: TradeSimulator | None = None,
    ) -> None:
        if (
            simulator is not None
            and not isinstance(
                simulator,
                TradeSimulator,
            )
        ):
            raise TypeError(
                "simulator must be a TradeSimulator instance"
            )

        self.simulator = (
            TradeSimulator()
            if simulator is None
            else simulator
        )

    def run(
        self,
        signals: Iterable[CandleSignal],
    ) -> list[TradePerformance]:
        """Simulate each signal once and return performance records."""

        iterator = _normalize_signal_iterator(
            signals,
        )

        results: list[TradePerformance] = []

        for index, signal in enumerate(iterator):
            if not isinstance(
                signal,
                CandleSignal,
            ):
                raise TypeError(
                    f"signals[{index}] must be a CandleSignal instance"
                )

            simulation = self.simulator.simulate(
                TradeRequest(
                    entry_price=signal.entry_price,
                    exit_price=signal.exit_price,
                    quantity=signal.quantity,
                )
            )

            if not isinstance(
                simulation,
                TradeSimulationResult,
            ):
                raise TypeError(
                    "simulator must return a "
                    "TradeSimulationResult instance"
                )

            results.append(
                TradePerformance(
                    strategy=signal.strategy,
                    symbol=signal.symbol,
                    timeframe=signal.timeframe,
                    pnl=simulation.net_profit,
                    risk_reward=signal.risk_reward,
                    win=simulation.net_profit > 0.0,
                    confidence=signal.confidence,
                    duration_minutes=signal.duration_minutes,
                )
            )

        return results


def _normalize_signal_iterator(
    signals: object,
) -> Iterator[object]:
    if isinstance(
        signals,
        (
            str,
            bytes,
            bytearray,
        ),
    ):
        raise TypeError(
            "signals must be an iterable of CandleSignal instances"
        )

    try:
        return iter(
            signals,  # type: ignore[arg-type]
        )
    except TypeError as exc:
        raise TypeError(
            "signals must be an iterable of CandleSignal instances"
        ) from exc


def _validate_non_empty_text(
    name: str,
    value: object,
) -> str:
    if not isinstance(value, str):
        raise TypeError(
            f"{name} must be a string"
        )

    if not value.strip():
        raise ValueError(
            f"{name} must not be empty"
        )

    return value


def _validate_number(
    name: str,
    value: object,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
    ):
        raise TypeError(
            f"{name} must be a real number"
        )

    number = float(value)

    if not isfinite(number):
        raise ValueError(
            f"{name} must be finite"
        )

    return number


def _validate_positive_number(
    name: str,
    value: object,
) -> float:
    number = _validate_number(
        name,
        value,
    )

    if number <= 0.0:
        raise ValueError(
            f"{name} must be greater than zero"
        )

    return number


def _validate_non_negative_number(
    name: str,
    value: object,
) -> float:
    number = _validate_number(
        name,
        value,
    )

    if number < 0.0:
        raise ValueError(
            f"{name} must be greater than or equal to zero"
        )

    return number


def _validate_percentage(
    name: str,
    value: object,
) -> float:
    number = _validate_number(
        name,
        value,
    )

    if not 0.0 <= number <= 100.0:
        raise ValueError(
            f"{name} must be between 0.0 and 100.0"
        )

    return number


def _validate_non_negative_integer(
    name: str,
    value: object,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
    ):
        raise TypeError(
            f"{name} must be an integer"
        )

    if value < 0:
        raise ValueError(
            f"{name} must be greater than or equal to zero"
        )

    return value


__all__ = [
    "CandleSignal",
    "StrategyRunner",
]