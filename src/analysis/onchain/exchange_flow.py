from dataclasses import dataclass


@dataclass
class ExchangeFlowResult:
    inflow: float
    outflow: float
    netflow: float
    signal: str


class ExchangeFlowEngine:

    def analyze(
        self,
        inflow: float,
        outflow: float,
    ) -> ExchangeFlowResult:

        netflow = inflow - outflow

        if netflow > 0:
            signal = "BEARISH"

        elif netflow < 0:
            signal = "BULLISH"

        else:
            signal = "NEUTRAL"

        return ExchangeFlowResult(
            inflow=inflow,
            outflow=outflow,
            netflow=netflow,
            signal=signal,
        )