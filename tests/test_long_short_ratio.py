from src.analysis.derivatives.long_short_ratio import LongShortRatioEngine

engine = LongShortRatioEngine()

print(engine.analyze(
    long_ratio=62,
    short_ratio=38,
))

print(engine.analyze(
    long_ratio=42,
    short_ratio=58,
))

print(engine.analyze(
    long_ratio=50,
    short_ratio=50,
))