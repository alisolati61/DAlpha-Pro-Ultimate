from dataclasses import dataclass


@dataclass
class CVDResult:
    buy_volume: float
    sell_volume: float
    delta: float
    cumulative_delta: float


class CVDEngine:

    def __init__(self):
        self.cumulative_delta = 0.0

    def update(
        self,
        buy_volume: float,
        sell_volume: float,
    ) -> CVDResult:

        delta = buy_volume - sell_volume

        self.cumulative_delta += delta

        return CVDResult(
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            delta=delta,
            cumulative_delta=self.cumulative_delta,
        )