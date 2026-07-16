from src.analysis.sentiment.news_intelligence import NewsIntelligenceEngine

engine = NewsIntelligenceEngine()

print(engine.analyze(
    "Bitcoin ETF Approved",
    0.95,
))

print(engine.analyze(
    "Major Exchange Hacked",
    -0.92,
))

print(engine.analyze(
    "Market Waiting For CPI",
    0.0,
))