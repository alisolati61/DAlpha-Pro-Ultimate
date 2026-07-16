from dataclasses import dataclass


@dataclass
class FootprintLevel:
    price: float
    buy_volume: float
    sell_volume: float
    delta: float


class FootprintEngine:

    def analyze(
        self,
        price: float,
        buy_volume: float,
        sell_volume: float,
    ) -> FootprintLevel:

        delta = buy_volume - sell_volume

        return FootprintLevel(
            price=price,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            delta=delta,
        )