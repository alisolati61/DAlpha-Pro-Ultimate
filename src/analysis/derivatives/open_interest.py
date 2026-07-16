from dataclasses import dataclass


@dataclass
class OpenInterestResult:
    current_oi: float
    previous_oi: float
    change_percent: float
    signal: str


class OpenInterestEngine:

    def analyze(
        self,
        current_oi: float,
        previous_oi: float,
    ) -> OpenInterestResult:

        if previous_oi == 0:
            change = 0
        else:
            change = (
                (current_oi - previous_oi)
                / previous_oi
            ) * 100

        if change > 5:
            signal = "INCREASING"

        elif change < -5:
            signal = "DECREASING"

        else:
            signal = "STABLE"

        return OpenInterestResult(
            current_oi=current_oi,
            previous_oi=previous_oi,
            change_percent=round(change, 2),
            signal=signal,
        )