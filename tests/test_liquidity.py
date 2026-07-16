from src.analysis.smart_money.liquidity import LiquidityEngine

engine = LiquidityEngine()

result = engine.detect(
    equal_high=True,
    equal_low=False,
    high_price=118500,
    low_price=116800,
)

print(result)