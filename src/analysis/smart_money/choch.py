from dataclasses import dataclass


@dataclass
class CHOCHResult:
    bullish_choch: bool
    bearish_choch: bool
    reversal_price: float | None


class CHOCHEngine:

    def detect(
        self,
        previous_trend: str,
        current_high: float,
        previous_high: float,
        current_low: float,
        previous_low: float,
    ) -> CHOCHResult:

        bullish = (
            previous_trend == "BEARISH"
            and current_high > previous_high
        )

        bearish = (
            previous_trend == "BULLISH"
            and current_low < previous_low
        )

        reversal = None

        if bullish:
            reversal = current_high

        elif bearish:
            reversal = current_low

        return CHOCHResult(
            bullish_choch=bullish,
            bearish_choch=bearish,
            reversal_price=reversal,
        )