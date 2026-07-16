from dataclasses import dataclass
from typing import Optional


@dataclass
class FairValueGap:
    bullish: bool
    bearish: bool
    top: Optional[float]
    bottom: Optional[float]
    valid: bool


class FairValueGapEngine:

    def detect(
        self,
        candle1_high: float,
        candle1_low: float,
        candle2_high: float,
        candle2_low: float,
        candle3_high: float,
        candle3_low: float,
    ) -> FairValueGap:

        bullish = candle3_low > candle1_high
        bearish = candle3_high < candle1_low

        if bullish:
            return FairValueGap(
                bullish=True,
                bearish=False,
                top=candle3_low,
                bottom=candle1_high,
                valid=True,
            )

        if bearish:
            return FairValueGap(
                bullish=False,
                bearish=True,
                top=candle1_low,
                bottom=candle3_high,
                valid=True,
            )

        return FairValueGap(
            bullish=False,
            bearish=False,
            top=None,
            bottom=None,
            valid=False,
        )