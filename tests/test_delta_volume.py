from src.analysis.orderflow.delta_volume import DeltaVolumeEngine

engine = DeltaVolumeEngine()

print(engine.analyze(250, 180))

print(engine.analyze(120, 220))

print(engine.analyze(150, 150))