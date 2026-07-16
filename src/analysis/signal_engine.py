from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Signal:

    direction: str

    confidence: float

    reason: str


class SignalEngine:

    def bullish(
        self,
        confidence: float,
        reason: str,
    ) -> Signal:

        return Signal(
            direction="BUY",
            confidence=confidence,
            reason=reason,
        )

    def bearish(
        self,
        confidence: float,
        reason: str,
    ) -> Signal:

        return Signal(
            direction="SELL",
            confidence=confidence,
            reason=reason,
        )

    def neutral(
        self,
        reason: str = "",
    ) -> Signal:

        return Signal(
            direction="NEUTRAL",
            confidence=0,
            reason=reason,
        )