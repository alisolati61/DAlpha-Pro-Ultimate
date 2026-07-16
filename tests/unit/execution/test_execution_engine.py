from src.drivers.paper_driver import PaperDriver
from src.execution.execution_engine import (
    ExecutionEngine,
    ExecutionRequest,
)
from src.execution.order_tracker import OrderTracker
from src.risk.circuit_breaker import CircuitBreaker
from src.risk.drawdown_guard import DrawdownGuard
from src.risk.kill_switch import KillSwitch
from src.risk.portfolio_guard import (
    PortfolioGuard,
    PortfolioState,
)
from src.risk.pre_trade_validator import PreTradeValidator
from src.risk.risk_orchestrator import RiskOrchestrator


def test_execution():

    risk = RiskOrchestrator(
        kill_switch=KillSwitch(),
        circuit_breaker=CircuitBreaker(),
        drawdown_guard=DrawdownGuard(),
        portfolio_guard=PortfolioGuard(),
        pre_trade_validator=PreTradeValidator(
            max_position_size=10,
            max_leverage=20,
        ),
    )

    engine = ExecutionEngine(
        risk=risk,
        exchange=PaperDriver(),
        tracker=OrderTracker(),
    )

    portfolio = PortfolioState(
        balance=10000,
        equity=10000,
        used_margin=1000,
        open_positions=1,
        daily_loss=0.01,
        total_risk=0.02,
    )

    request = ExecutionRequest(
        symbol="BTCUSDT",
        quantity=2,
        price=100000,
        leverage=5,
        stop_loss=99000,
        portfolio=portfolio,
    )

    assert engine.execute(request)