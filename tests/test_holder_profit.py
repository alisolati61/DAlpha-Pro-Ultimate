from src.analysis.onchain.holder_profit import HolderProfitLossEngine

engine = HolderProfitLossEngine()

print(engine.analyze(
    average_cost=100000,
    current_price=118000,
))

print(engine.analyze(
    average_cost=120000,
    current_price=118000,
))