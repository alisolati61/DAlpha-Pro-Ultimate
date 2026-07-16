from src.infrastructure.connectors.validator import DataValidationEngine

engine = DataValidationEngine()

prices = [
    118500,
    118490,
    118510,
    118505,
    500000,      # Outlier
]

print(engine.validate_price(prices))

print(
    engine.validate_data(
        {
            "price":118500,
            "volume":12345,
            "oi":5678,
        }
    )
)