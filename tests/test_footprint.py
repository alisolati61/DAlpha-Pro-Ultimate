from src.analysis.orderflow.footprint import FootprintEngine

engine = FootprintEngine()

result = engine.analyze(
    price=118500,
    buy_volume=420,
    sell_volume=300,
)

print(result)