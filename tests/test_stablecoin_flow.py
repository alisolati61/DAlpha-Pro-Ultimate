from src.analysis.onchain.stablecoins import StablecoinFlowEngine

engine = StablecoinFlowEngine()

print(engine.analyze(
    inflow=150000000,
    outflow=90000000,
))

print(engine.analyze(
    inflow=70000000,
    outflow=120000000,
))

print(engine.analyze(
    inflow=50000000,
    outflow=50000000,
))