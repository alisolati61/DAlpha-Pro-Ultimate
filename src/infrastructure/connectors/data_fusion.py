from typing import Dict


class DataFusionEngine:

    def merge(self, *sources: Dict) -> Dict:

        merged = {}

        for source in sources:
            merged.update(source)

        return merged