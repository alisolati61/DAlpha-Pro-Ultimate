from src.ai.feedback_loop import (
    FeedbackEvent,
    FeedbackLoop,
)


def test_feedback_initial_state():

    loop = FeedbackLoop()

    assert loop.total_events == 0
    assert loop.successful_events == 0
    assert loop.failed_events == 0
    assert loop.success_rate == 0.0


def test_record_success():

    loop = FeedbackLoop()

    loop.record(
        FeedbackEvent(
            strategy="SMC",
            symbol="BTCUSDT",
            success=True,
            expected_confidence=85.0,
            actual_profit=150.0,
        )
    )

    assert loop.total_events == 1
    assert loop.successful_events == 1
    assert loop.failed_events == 0


def test_record_failure():

    loop = FeedbackLoop()

    loop.record(
        FeedbackEvent(
            strategy="ICT",
            symbol="ETHUSDT",
            success=False,
            expected_confidence=75.0,
            actual_profit=-80.0,
        )
    )

    assert loop.total_events == 1
    assert loop.successful_events == 0
    assert loop.failed_events == 1


def test_success_rate():

    loop = FeedbackLoop()

    loop.record(
        FeedbackEvent(
            strategy="A",
            symbol="BTC",
            success=True,
            expected_confidence=80,
            actual_profit=50,
        )
    )

    loop.record(
        FeedbackEvent(
            strategy="A",
            symbol="BTC",
            success=False,
            expected_confidence=60,
            actual_profit=-20,
        )
    )

    assert loop.success_rate == 50.0


def test_strategy_history():

    loop = FeedbackLoop()

    loop.record(
        FeedbackEvent(
            strategy="SMC",
            symbol="BTC",
            success=True,
            expected_confidence=80,
            actual_profit=100,
        )
    )

    loop.record(
        FeedbackEvent(
            strategy="ICT",
            symbol="BTC",
            success=True,
            expected_confidence=70,
            actual_profit=50,
        )
    )

    history = loop.strategy_history("SMC")

    assert len(history) == 1
    assert history[0].strategy == "SMC"


def test_symbol_history():

    loop = FeedbackLoop()

    loop.record(
        FeedbackEvent(
            strategy="SMC",
            symbol="BTCUSDT",
            success=True,
            expected_confidence=80,
            actual_profit=100,
        )
    )

    loop.record(
        FeedbackEvent(
            strategy="SMC",
            symbol="ETHUSDT",
            success=True,
            expected_confidence=80,
            actual_profit=100,
        )
    )

    btc = loop.symbol_history("BTCUSDT")

    assert len(btc) == 1
    assert btc[0].symbol == "BTCUSDT"


def test_clear_feedback():

    loop = FeedbackLoop()

    loop.record(
        FeedbackEvent(
            strategy="SMC",
            symbol="BTC",
            success=True,
            expected_confidence=80,
            actual_profit=100,
        )
    )

    loop.clear()

    assert loop.total_events == 0