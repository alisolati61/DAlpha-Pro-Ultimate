from src.analysis.orderflow.cvd import CVDEngine

engine = CVDEngine()

print(engine.update(150, 100))

print(engine.update(90, 140))

print(engine.update(200, 120))