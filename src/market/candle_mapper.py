from src.domain.candle import Candle
from src.domain.candle_series import CandleSeries


class CandleMapper:
    """
    Converts CCXT OHLCV data into CandleSeries.
    """

    @staticmethod
    def from_ohlcv(
        symbol: str,
        timeframe: str,
        ohlcv: list[list],
    ) -> CandleSeries:

        series = CandleSeries(
            symbol=symbol,
            timeframe=timeframe,
        )

        for row in ohlcv:

            candle = Candle(
                timestamp=row[0],
                open=row[1],
                high=row[2],
                low=row[3],
                close=row[4],
                volume=row[5],
            )

            series.add(candle)

        return series