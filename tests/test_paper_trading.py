from src.execution.paper_trading import PaperTradingEngine

engine = PaperTradingEngine()

trade = engine.execute(
    "BTC/USDT",
    "BUY",
    0.01,
    118500,
)

print(trade)

print(engine.history())