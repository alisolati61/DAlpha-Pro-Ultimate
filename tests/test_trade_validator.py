from src.decision import (
    DecisionInput,
    TradeValidator,
)


def test_trade_validator_accept():

    decision = DecisionInput(
        risk_score=80,
    )

    approved, reason = TradeValidator.validate(
        decision
    )

    assert approved is True
    assert reason == "Trade approved"


def test_trade_validator_reject():

    decision = DecisionInput(
        risk_score=30,
    )

    approved, reason = TradeValidator.validate(
        decision
    )

    assert approved is False
    assert reason == "Risk manager rejected trade"