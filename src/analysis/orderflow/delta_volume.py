from dataclasses import dataclass


@dataclass
class DeltaVolumeResult:
    buy_volume: float
    sell_volume: float
    delta: float
    pressure: str


class DeltaVolumeEngine:

    def analyze(
        self,
        buy_volume: float,
        sell_volume: float,
    ) -> DeltaVolumeResult:

        delta = buy_volume - sell_volume

        if delta > 0:
            pressure = "BUY"

        elif delta < 0:
            pressure = "SELL"

        else:
            pressure = "NEUTRAL"

        return DeltaVolumeResult(
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            delta=delta,
            pressure=pressure,
        )