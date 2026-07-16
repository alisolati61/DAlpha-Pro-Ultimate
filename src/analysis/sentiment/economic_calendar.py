from dataclasses import dataclass
from datetime import datetime


@dataclass
class EconomicEvent:

    name: str

    currency: str

    impact: str

    event_time: datetime

    trading_allowed: bool


class EconomicCalendarEngine:

    HIGH_IMPACT = {
        "FOMC",
        "CPI",
        "PPI",
        "NFP",
        "GDP",
        "Interest Rate",
    }

    def analyze(

        self,

        name: str,

        currency: str,

        event_time: datetime,

    ) -> EconomicEvent:

        if name in self.HIGH_IMPACT:

            impact = "HIGH"

            trading = False

        else:

            impact = "LOW"

            trading = True

        return EconomicEvent(

            name=name,

            currency=currency,

            impact=impact,

            event_time=event_time,

            trading_allowed=trading,

        )