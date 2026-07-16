from src.infrastructure.connectors.data_fusion import DataFusionEngine

engine = DataFusionEngine()

price = {
    "price": 118500
}

onchain = {
    "exchange_outflow": 2500
}

sentiment = {
    "fear_greed": 68
}

result = engine.merge(
    price,
    onchain,
    sentiment,
)

print(result)