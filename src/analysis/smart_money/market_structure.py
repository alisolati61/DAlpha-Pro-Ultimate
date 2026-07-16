from dataclasses import dataclass
from enum import Enum
from typing import List


class Trend(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    SIDEWAYS = "SIDEWAYS"


@dataclass
class SwingPoint:
    index: int
    price: float


@dataclass
class MarketStructure:

    trend: Trend

    higher_highs: List[SwingPoint]

    higher_lows: List[SwingPoint]

    lower_highs: List[SwingPoint]

    lower_lows: List[SwingPoint]


class MarketStructureEngine:

    def analyze(self, highs, lows):

        if len(highs) < 2 or len(lows) < 2:

            return MarketStructure(
                trend=Trend.SIDEWAYS,
                higher_highs=[],
                higher_lows=[],
                lower_highs=[],
                lower_lows=[],
            )

        if highs[-1] > highs[-2] and lows[-1] > lows[-2]:

            trend = Trend.BULLISH

        elif highs[-1] < highs[-2] and lows[-1] < lows[-2]:

            trend = Trend.BEARISH

        else:

            trend = Trend.SIDEWAYS

        return MarketStructure(
            trend=trend,
            higher_highs=[],
            higher_lows=[],
            lower_highs=[],
            lower_lows=[],
        )