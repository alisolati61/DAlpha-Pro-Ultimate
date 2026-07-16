from dataclasses import dataclass


@dataclass
class StrategyResult:
    strategy: str
    timeframe: str


class StrategySelector:

    def select(self, regime: str, volatility: str) -> StrategyResult:

        if regime == "TREND":

            if volatility == "HIGH":
                return StrategyResult(
                    strategy="Trend Following",
                    timeframe="15m-1H",
                )

            return StrategyResult(
                strategy="Swing Trend",
                timeframe="1H-4H",
            )

        if regime == "RANGE":

            return StrategyResult(
                strategy="Mean Reversion",
                timeframe="5m-15m",
            )

        return StrategyResult(
            strategy="Wait",
            timeframe="-",
        )