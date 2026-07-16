from src.analysis.smart_money.bos import BOSEngine

engine = BOSEngine()

result = engine.detect(
    previous_high=118000,
    previous_low=116000,
    current_high=118600,
    current_low=116500,
)

print(result)