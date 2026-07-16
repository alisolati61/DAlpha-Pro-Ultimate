from src.analysis.derivatives.funding_rate import FundingRateEngine

engine = FundingRateEngine()

print(engine.analyze(0.015))

print(engine.analyze(-0.018))

print(engine.analyze(0.002))