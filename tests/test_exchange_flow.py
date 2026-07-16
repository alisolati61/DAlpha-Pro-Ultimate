from src.analysis.onchain.exchange_flow import ExchangeFlowEngine

engine = ExchangeFlowEngine()

print(engine.analyze(
    inflow=12000,
    outflow=8000,
))

print(engine.analyze(
    inflow=5000,
    outflow=12000,
))

print(engine.analyze(
    inflow=9000,
    outflow=9000,
))