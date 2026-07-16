from src.backtesting.backtest_engine import BacktestEngine

engine = BacktestEngine()

trades = [
    120,
    -50,
    90,
    40,
    -30,
    150,
    -70,
]

result = engine.evaluate(trades)

print(result)