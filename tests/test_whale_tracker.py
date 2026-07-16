from src.analysis.onchain.whale_tracker import WhaleTrackerEngine

engine = WhaleTrackerEngine()

print(engine.analyze(
    transaction_value=2_500_000,
    direction="IN",
))

print(engine.analyze(
    transaction_value=250_000,
    direction="OUT",
))