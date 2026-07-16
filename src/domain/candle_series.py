from dataclasses import dataclass, field

from src.domain.candle import Candle


@dataclass(slots=True)
class CandleSeries:
    symbol: str

    timeframe: str

    candles: list[Candle] = field(default_factory=list)

    def add(self, candle: Candle) -> None:
        self.candles.append(candle)

    def last(self) -> Candle | None:
        if not self.candles:
            return None

        return self.candles[-1]

    def __len__(self) -> int:
        return len(self.candles)