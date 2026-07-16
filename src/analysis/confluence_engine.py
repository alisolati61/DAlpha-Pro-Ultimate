from __future__ import annotations

from src.analysis.signal_engine import Signal


class ConfluenceEngine:
    """
    Combines multiple trading signals into a single decision.
    """

    def combine(
        self,
        signals: list[Signal],
    ) -> Signal:

        if not signals:
            return Signal(
                direction="NEUTRAL",
                confidence=0,
                reason="No Signals",
            )

        buy_score = 0.0
        sell_score = 0.0

        buy_reasons = []
        sell_reasons = []

        for signal in signals:

            if signal.direction == "BUY":

                buy_score += signal.confidence

                buy_reasons.append(signal.reason)

            elif signal.direction == "SELL":

                sell_score += signal.confidence

                sell_reasons.append(signal.reason)

        if buy_score > sell_score:

            return Signal(
                direction="BUY",
                confidence=round(buy_score / len(signals), 2),
                reason=" | ".join(buy_reasons),
            )

        if sell_score > buy_score:

            return Signal(
                direction="SELL",
                confidence=round(sell_score / len(signals), 2),
                reason=" | ".join(sell_reasons),
            )

        return Signal(
            direction="NEUTRAL",
            confidence=0,
            reason="Conflict",
        )