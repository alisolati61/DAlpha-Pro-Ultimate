from src.analysis.technical.market_profile import MarketProfileEngine

engine = MarketProfileEngine()

result = engine.analyze(
    [
        117000,
        117500,
        118000,
        118500,
        119000,
    ]
)

print(result)