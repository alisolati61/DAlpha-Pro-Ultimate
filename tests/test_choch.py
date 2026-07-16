from src.analysis.smart_money.choch import CHOCHEngine

engine = CHOCHEngine()

result = engine.detect(
    previous_trend="BEARISH",
    previous_high=118000,
    current_high=118800,
    previous_low=116000,
    current_low=116300,
)

print(result)