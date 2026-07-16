from dataclasses import dataclass


@dataclass
class StablecoinFlow:
    inflow: float
    outflow: float
    netflow: float
    liquidity_signal: str


class StablecoinFlowEngine:

    def analyze(
        self,
        inflow: float,
        outflow: float,
    ) -> StablecoinFlow:

        netflow = inflow - outflow

        if netflow > 0:
            signal = "HIGH_LIQUIDITY"

        elif netflow < 0:
            signal = "LOW_LIQUIDITY"

        else:
            signal = "NEUTRAL"

        return StablecoinFlow(
            inflow=inflow,
            outflow=outflow,
            netflow=netflow,
            liquidity_signal=signal,
        )