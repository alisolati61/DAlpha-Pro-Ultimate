from dataclasses import dataclass


@dataclass
class BOSResult:
    bullish_bos: bool
    bearish_bos: bool
    breakout_price: float | None


class BOSEngine:

    def detect(
        self,
        previous_high: float,
        previous_low: float,
        current_high: float,
        current_low: float,
    ) -> BOSResult:

        bullish = current_high > previous_high

        bearish = current_low < previous_low

        breakout = None

        if bullish:
            breakout = current_high

        elif bearish:
            breakout = current_low

        return BOSResult(
            bullish_bos=bullish,
            bearish_bos=bearish,
            breakout_price=breakout,
        )