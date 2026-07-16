from dataclasses import dataclass


@dataclass
class MarketSentiment:

    fear_greed_index: int

    sentiment: str

    confidence: float


class MarketSentimentEngine:

    def analyze(
        self,
        fear_greed_index: int,
    ) -> MarketSentiment:

        if fear_greed_index <= 25:

            sentiment = "EXTREME_FEAR"

            confidence = 0.90

        elif fear_greed_index <= 45:

            sentiment = "FEAR"

            confidence = 0.70

        elif fear_greed_index <= 55:

            sentiment = "NEUTRAL"

            confidence = 0.50

        elif fear_greed_index <= 75:

            sentiment = "GREED"

            confidence = 0.70

        else:

            sentiment = "EXTREME_GREED"

            confidence = 0.90

        return MarketSentiment(
            fear_greed_index=fear_greed_index,
            sentiment=sentiment,
            confidence=confidence,
        )