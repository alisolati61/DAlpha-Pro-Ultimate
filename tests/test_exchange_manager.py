from src.exchange.manager import ExchangeManager

manager = ExchangeManager()

manager.register("binance")
manager.register("bybit")
manager.register("okx")
manager.register("coinex")

print(manager.list())