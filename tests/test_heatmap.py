from src.analysis.derivatives.heatmap import HeatmapEngine

engine = HeatmapEngine()

print(engine.analyze(
    liquidity_level=4200000,
    average_liquidity=1000000,
))

print(engine.analyze(
    liquidity_level=2200000,
    average_liquidity=1000000,
))

print(engine.analyze(
    liquidity_level=900000,
    average_liquidity=1000000,
))