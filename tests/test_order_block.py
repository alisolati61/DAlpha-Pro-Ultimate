from src.analysis.smart_money.order_block import OrderBlockEngine

engine = OrderBlockEngine()

result = engine.detect(
    candle_open=117800,
    candle_close=118500,
    candle_high=118700,
    candle_low=117500,
)

print(result)