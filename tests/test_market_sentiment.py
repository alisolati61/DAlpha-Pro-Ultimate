from src.analysis.sentiment.market_sentiment import MarketSentimentEngine

engine = MarketSentimentEngine()

print(engine.analyze(18))

print(engine.analyze(42))

print(engine.analyze(53))

print(engine.analyze(68))

print(engine.analyze(91))