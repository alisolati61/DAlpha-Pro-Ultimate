from src.risk.position_sizer import PositionSizer

sizer = PositionSizer()

size = sizer.calculate_position_size(
    balance=10000,
    risk_percent=0.01,
    entry_price=120000,
    stop_loss=118000,
)

print(size)