from src.risk.drawdown_guard import DrawdownGuard

guard = DrawdownGuard(max_drawdown=0.15)

peak = 10000

print(guard.calculate_drawdown(peak, 9500))
print(guard.can_continue(peak, 9500))

print(guard.calculate_drawdown(peak, 8000))
print(guard.can_continue(peak, 8000))