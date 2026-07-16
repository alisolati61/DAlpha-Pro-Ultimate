from src.decision import (
    DecisionEngine,
    DecisionInput,
)


def test_buy_decision():

    engine = DecisionEngine()

    result = engine.evaluate(
        DecisionInput(
            technical_score=90,
            smart_money_score=90,
            orderflow_score=80,
            sentiment_score=70,
            onchain_score=80,
            risk_score=100,
        )
    )

    assert result.action == "BUY"


def test_hold_when_score_low():

    engine = DecisionEngine()

    result = engine.evaluate(
        DecisionInput(
            technical_score=20,
            smart_money_score=20,
            orderflow_score=30,
            sentiment_score=20,
            onchain_score=30,
            risk_score=100,
        )
    )

    assert result.action == "HOLD"


def test_hold_when_risk_rejects():

    engine = DecisionEngine()

    result = engine.evaluate(
        DecisionInput(
            technical_score=100,
            smart_money_score=100,
            orderflow_score=100,
            sentiment_score=100,
            onchain_score=100,
            risk_score=20,
        )
    )

    assert result.action == "HOLD"
    assert result.reason == "Risk manager rejected trade"


def test_confidence_range():

    engine = DecisionEngine()

    result = engine.evaluate(
        DecisionInput(
            technical_score=80,
            smart_money_score=80,
            orderflow_score=80,
            sentiment_score=80,
            onchain_score=80,
            risk_score=100,
        )
    )

    assert 0 <= result.confidence <= 1