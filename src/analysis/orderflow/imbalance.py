from dataclasses import dataclass


@dataclass
class ImbalanceResult:
    imbalance_ratio: float
    bullish: bool
    bearish: bool


class ImbalanceEngine:

    def analyze(
        self,
        buy_volume: float,
        sell_volume: float,
    ) -> ImbalanceResult:

        total = buy_volume + sell_volume

        if total == 0:
            ratio = 0
        else:
            ratio = (buy_volume - sell_volume) / total

        return ImbalanceResult(
            imbalance_ratio=ratio,
            bullish=ratio > 0.2,
            bearish=ratio < -0.2,
        )