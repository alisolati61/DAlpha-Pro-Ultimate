from src.execution.order_manager import OrderManager

manager = OrderManager()

market = manager.create_market_order(
    "BTC/USDT",
    "buy",
    0.01
)

limit = manager.create_limit_order(
    "BTC/USDT",
    "sell",
    0.01,
    120000
)

print(market)
print(limit)