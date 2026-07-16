from src.analysis.smart_money.fair_value_gap import FairValueGapEngine

engine = FairValueGapEngine()

result = engine.detect(
    candle1_high=118000,
    candle1_low=117000,
    candle2_high=118500,
    candle2_low=117500,
    candle3_high=119500,
    candle3_low=118300,
)

print(result)