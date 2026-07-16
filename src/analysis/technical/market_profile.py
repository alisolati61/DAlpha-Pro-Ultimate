from dataclasses import dataclass


@dataclass
class MarketProfile:
    poc: float
    value_area_high: float
    value_area_low: float


class MarketProfileEngine:

    def analyze(self, prices):

        if not prices:
            return MarketProfile(
                poc=0,
                value_area_high=0,
                value_area_low=0,
            )

        poc = prices[len(prices) // 2]

        return MarketProfile(
            poc=poc,
            value_area_high=max(prices),
            value_area_low=min(prices),
        )