from dataclasses import dataclass


@dataclass
class LiquidationResult:
    long_liquidation: float
    short_liquidation: float
    dominant_side: str
    pressure: str


class LiquidationEngine:

    def analyze(
        self,
        long_liquidation: float,
        short_liquidation: float,
    ) -> LiquidationResult:

        if long_liquidation > short_liquidation:

            dominant = "LONGS"

            pressure = "BEARISH"

        elif short_liquidation > long_liquidation:

            dominant = "SHORTS"

            pressure = "BULLISH"

        else:

            dominant = "BALANCED"

            pressure = "NEUTRAL"

        return LiquidationResult(
            long_liquidation=long_liquidation,
            short_liquidation=short_liquidation,
            dominant_side=dominant,
            pressure=pressure,
        )