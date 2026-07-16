from typing import Dict


class ScoringEngine:

    def calculate(self, signals: Dict[str, float]) -> Dict[str, float]:

        weights = {
            "trend": 0.20,
            "volume": 0.15,
            "onchain": 0.20,
            "orderflow": 0.20,
            "sentiment": 0.10,
            "risk": 0.15,
        }

        scores = {}

        for key, value in signals.items():
            scores[key] = value * weights.get(key, 0)

        return scores