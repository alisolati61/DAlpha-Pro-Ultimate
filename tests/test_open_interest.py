from src.analysis.derivatives.open_interest import OpenInterestEngine

engine = OpenInterestEngine()

print(engine.analyze(
    current_oi=12_600_000_000,
    previous_oi=12_000_000_000,
))

print(engine.analyze(
    current_oi=11_200_000_000,
    previous_oi=12_000_000_000,
))