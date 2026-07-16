from dataclasses import dataclass


@dataclass
class WhaleActivity:
    transaction_value: float
    is_whale: bool
    direction: str


class WhaleTrackerEngine:

    WHALE_THRESHOLD = 1_000_000  # USD

    def analyze(
        self,
        transaction_value: float,
        direction: str,
    ) -> WhaleActivity:

        return WhaleActivity(
            transaction_value=transaction_value,
            is_whale=transaction_value >= self.WHALE_THRESHOLD,
            direction=direction.upper(),
        )