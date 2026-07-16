from dataclasses import dataclass


@dataclass
class NewsAnalysis:
    title: str
    impact: str
    sentiment: str
    score: float


class NewsIntelligenceEngine:

    def analyze(
        self,
        title: str,
        sentiment_score: float,
    ) -> NewsAnalysis:

        if sentiment_score >= 0.7:
            impact = "HIGH"
            sentiment = "BULLISH"

        elif sentiment_score <= -0.7:
            impact = "HIGH"
            sentiment = "BEARISH"

        elif sentiment_score > 0:
            impact = "MEDIUM"
            sentiment = "POSITIVE"

        elif sentiment_score < 0:
            impact = "MEDIUM"
            sentiment = "NEGATIVE"

        else:
            impact = "LOW"
            sentiment = "NEUTRAL"

        return NewsAnalysis(
            title=title,
            impact=impact,
            sentiment=sentiment,
            score=sentiment_score,
        )