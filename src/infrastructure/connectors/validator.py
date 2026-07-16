from typing import Dict, List


class DataValidationEngine:

    def validate_price(self, prices: List[float]) -> float:
        """
        Returns the median price after removing invalid values.
        """
        valid = [p for p in prices if p > 0]

        if not valid:
            raise ValueError("No valid prices found.")

        valid.sort()

        n = len(valid)

        if n % 2 == 1:
            return valid[n // 2]

        return (valid[n // 2 - 1] + valid[n // 2]) / 2

    def validate_data(self, data: Dict) -> bool:
        return all(value is not None for value in data.values())