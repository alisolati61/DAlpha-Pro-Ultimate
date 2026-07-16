from dataclasses import dataclass


@dataclass
class AbsorptionResult:
    absorbed: bool
    side: str
    strength: float


class AbsorptionEngine:

    def analyze(
        self,
        aggressive_buy: float,
        aggressive_sell: float,
        price_change: float,
    ) -> AbsorptionResult:

        if aggressive_buy > aggressive_sell and abs(price_change) < 0.1:
            return AbsorptionResult(
                absorbed=True,
                side="SELLER",
                strength=aggressive_buy,
            )

        if aggressive_sell > aggressive_buy and abs(price_change) < 0.1:
            return AbsorptionResult(
                absorbed=True,
                side="BUYER",
                strength=aggressive_sell,
            )

        return AbsorptionResult(
            absorbed=False,
            side="NONE",
            strength=0,
        )