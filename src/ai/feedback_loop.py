from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import List


@dataclass(slots=True)
class FeedbackEvent:
    """
    Represents feedback generated after a completed trade.
    """

    strategy: str
    symbol: str
    success: bool

    expected_confidence: float
    actual_profit: float

    notes: str = ""

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )


class FeedbackLoop:
    """
    AI Feedback Loop.

    Responsible for collecting trade outcomes and
    preparing learning signals for future optimization.

    Future versions:

    - Reinforcement Learning
    - Neural Network feedback
    - Dynamic Strategy Ranking
    - Confidence Calibration
    """

    def __init__(self) -> None:

        self._events: List[FeedbackEvent] = []

    # --------------------------------------------------

    def record(
        self,
        event: FeedbackEvent,
    ) -> None:

        self._events.append(event)

    # --------------------------------------------------

    @property
    def total_events(self) -> int:

        return len(self._events)

    # --------------------------------------------------

    @property
    def successful_events(self) -> int:

        return sum(
            event.success
            for event in self._events
        )

    # --------------------------------------------------

    @property
    def failed_events(self) -> int:

        return self.total_events - self.successful_events

    # --------------------------------------------------

    @property
    def success_rate(self) -> float:

        if self.total_events == 0:
            return 0.0

        return round(
            (self.successful_events / self.total_events)
            * 100,
            2,
        )

    # --------------------------------------------------

    def strategy_history(
        self,
        strategy: str,
    ) -> List[FeedbackEvent]:

        return [
            event
            for event in self._events
            if event.strategy == strategy
        ]

    # --------------------------------------------------

    def symbol_history(
        self,
        symbol: str,
    ) -> List[FeedbackEvent]:

        return [
            event
            for event in self._events
            if event.symbol == symbol
        ]

    # --------------------------------------------------

    def clear(self) -> None:

        self._events.clear()