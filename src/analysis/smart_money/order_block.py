from dataclasses import dataclass


@dataclass
class OrderBlock:
    bullish: bool
    bearish: bool
    high: float
    low: float
    valid: bool


class OrderBlockEngine:

    def detect(
        self,
        candle_open: float,
        candle_close: float,
        candle_high: float,
        candle_low: float,
    ) -> OrderBlock:

        bullish = candle_close > candle_open
        bearish = candle_close < candle_open

        return OrderBlock(
            bullish=bullish,
            bearish=bearish,
            high=candle_high,
            low=candle_low,
            valid=True,
        )