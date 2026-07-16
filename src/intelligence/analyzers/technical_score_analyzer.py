from src.analysis.technical.atr import ATRAnalyzer
from src.analysis.technical.macd import MACDAnalyzer
from src.analysis.technical.rsi import RSIAnalyzer
from src.analysis.technical.ema import EMAAnalyzer
from src.domain.candle_series import CandleSeries


class TechnicalScoreAnalyzer:
    """
    Combines multiple technical indicators into
    one normalized score (0-100).
    """

    @staticmethod
    def score(series: CandleSeries) -> float:

        scores = []

        # RSI
        rsi = RSIAnalyzer.calculate(series)
        if rsi is not None:

            if 40 <= rsi <= 60:
                scores.append(100)

            elif rsi < 40:
                scores.append(max(0, rsi / 40 * 100))

            else:
                scores.append(max(0, (100 - rsi) / 40 * 100))

        # EMA
        if EMAAnalyzer.is_above_ema(series):
            scores.append(100)
        else:
            scores.append(40)

        # MACD
        scores.append(
            MACDAnalyzer.score(series)
        )

        # ATR
        scores.append(
            ATRAnalyzer.volatility_score(series)
        )

        if not scores:
            return 50.0

        return round(sum(scores) / len(scores), 2)