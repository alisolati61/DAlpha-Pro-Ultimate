from dataclasses import dataclass


@dataclass
class IntermarketResult:

    dxy: float

    gold: float

    sp500: float

    btc_dominance: float

    usdt_dominance: float

    market_bias: str


class IntermarketEngine:

    def analyze(

        self,

        dxy: float,

        gold: float,

        sp500: float,

        btc_dominance: float,

        usdt_dominance: float,

    ) -> IntermarketResult:

        score = 0

        if dxy < 100:
            score += 1
        else:
            score -= 1

        if gold > 0:
            score += 1

        if sp500 > 0:
            score += 1

        if btc_dominance > 55:
            score += 1

        if usdt_dominance < 6:
            score += 1

        if score >= 3:
            bias = "BULLISH"

        elif score <= -2:
            bias = "BEARISH"

        else:
            bias = "NEUTRAL"

        return IntermarketResult(

            dxy=dxy,

            gold=gold,

            sp500=sp500,

            btc_dominance=btc_dominance,

            usdt_dominance=usdt_dominance,

            market_bias=bias,

        )