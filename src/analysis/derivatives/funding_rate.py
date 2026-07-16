from dataclasses import dataclass


@dataclass
class FundingRateResult:
    funding_rate: float
    bias: str
    sentiment: str


class FundingRateEngine:

    def analyze(
        self,
        funding_rate: float,
    ) -> FundingRateResult:

        if funding_rate > 0.01:
            bias = "LONGS_CROWDED"
            sentiment = "BEARISH"

        elif funding_rate < -0.01:
            bias = "SHORTS_CROWDED"
            sentiment = "BULLISH"

        else:
            bias = "BALANCED"
            sentiment = "NEUTRAL"

        return FundingRateResult(
            funding_rate=funding_rate,
            bias=bias,
            sentiment=sentiment,
        )