from src.risk.circuit_breaker import CircuitBreaker


def test_normal_operation():

    breaker = CircuitBreaker()

    assert breaker.can_trade()


def test_activation():

    breaker = CircuitBreaker(
        max_consecutive_losses=3
    )

    breaker.register_trade(-10)
    breaker.register_trade(-5)
    breaker.register_trade(-8)

    assert not breaker.can_trade()


def test_reset_after_profit():

    breaker = CircuitBreaker(
        max_consecutive_losses=3
    )

    breaker.register_trade(-5)
    breaker.register_trade(10)

    assert breaker.loss_counter == 0