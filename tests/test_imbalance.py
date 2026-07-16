from src.analysis.orderflow.imbalance import ImbalanceEngine

engine = ImbalanceEngine()

print(engine.analyze(300, 100))

print(engine.analyze(120, 250))

print(engine.analyze(150, 150))