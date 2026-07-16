from src.execution.position_manager import PositionManager, Position

manager = PositionManager()

position = Position(
    symbol="BTC/USDT",
    side="BUY",
    size=0.02,
    entry_price=118500,
)

manager.open_position(position)

print(manager.list_positions())

print(manager.get_position("BTC/USDT"))

manager.close_position("BTC/USDT")

print(manager.list_positions())