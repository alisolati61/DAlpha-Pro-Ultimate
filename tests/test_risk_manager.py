from src.risk.risk_manager import RiskManager

manager = RiskManager()

balance = 10000

print(manager.calculate_risk_amount(balance))

print(manager.can_trade(0.02))

print(manager.can_trade(0.06))