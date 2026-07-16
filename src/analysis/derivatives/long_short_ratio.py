from dataclasses import dataclass


@dataclass
class LongShortRatioResult:
    long_ratio: float
    short_ratio: float
    ratio: float
    sentiment: str


class LongShortRatioEngine:

    def analyze(
        self,
        long_ratio: float,
        short_ratio: float,
    ) -> LongShortRatioResult:

        if short_ratio == 0:
            ratio = 0
        else:
            ratio = long_ratio / short_ratio

        if ratio > 1.2:
            sentiment = "LONG_BIAS"

        elif ratio < 0.8:
            sentiment = "SHORT_BIAS"

        else:
            sentiment = "BALANCED"

        return LongShortRatioResult(
            long_ratio=long_ratio,
            short_ratio=short_ratio,
            ratio=round(ratio, 2),
            sentiment=sentiment,
        )