from src.decision.models import (
    DecisionInput,
    DecisionResult,
)


def test_decision_input_defaults():

    decision = DecisionInput()

    assert decision.technical_score == 0.0
    assert decision.smart_money_score == 0.0
    assert decision.orderflow_score == 0.0
    assert decision.sentiment_score == 0.0
    assert decision.onchain_score == 0.0
    assert decision.risk_score == 100.0


def test_decision_input_values():

    decision = DecisionInput(
        technical_score=80,
        smart_money_score=90,
        orderflow_score=70,
        sentiment_score=60,
        onchain_score=50,
        risk_score=95,
    )

    assert decision.technical_score == 80
    assert decision.smart_money_score == 90
    assert decision.orderflow_score == 70
    assert decision.sentiment_score == 60
    assert decision.onchain_score == 50
    assert decision.risk_score == 95


def test_decision_result_creation():

    result = DecisionResult(
        action="BUY",
        confidence=0.91,
        final_score=88.5,
        scores={
            "technical": 90,
            "smart_money": 85,
        },
        reason="Strong confirmation",
    )

    assert result.action == "BUY"
    assert result.confidence == 0.91
    assert result.final_score == 88.5
    assert result.scores["technical"] == 90
    assert result.reason == "Strong confirmation"