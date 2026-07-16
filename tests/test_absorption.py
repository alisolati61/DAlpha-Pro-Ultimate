from src.analysis.orderflow.absorption import AbsorptionEngine

engine = AbsorptionEngine()

print(engine.analyze(
    aggressive_buy=500,
    aggressive_sell=250,
    price_change=0.03,
))

print(engine.analyze(
    aggressive_buy=180,
    aggressive_sell=420,
    price_change=0.05,
))

print(engine.analyze(
    aggressive_buy=300,
    aggressive_sell=280,
    price_change=1.5,
))