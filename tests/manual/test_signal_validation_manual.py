from src.ai.signal_validation import SignalValidationEngine

engine = SignalValidationEngine()

scores = {
    "trend": 15,
    "smc": 15,
    "orderflow": 15,
    "risk": 10,
}

print(engine.validate(scores))

scores2 = {
    "trend": 5,
    "smc": 15,
    "orderflow": 8,
    "risk": 10,
}

print(engine.validate(scores2))