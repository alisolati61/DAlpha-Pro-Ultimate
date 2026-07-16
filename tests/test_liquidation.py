from src.analysis.derivatives.liquidation import LiquidationEngine

engine = LiquidationEngine()

print(engine.analyze(
    long_liquidation=185_000_000,
    short_liquidation=70_000_000,
))

print(engine.analyze(
    long_liquidation=40_000_000,
    short_liquidation=210_000_000,
))

print(engine.analyze(
    long_liquidation=95_000_000,
    short_liquidation=95_000_000,
))