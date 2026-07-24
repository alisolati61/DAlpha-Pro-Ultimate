"""Tests for validated historical strategy execution."""

from dataclasses import FrozenInstanceError
from math import inf, nan

import pytest

from src.ai.performance_tracker import TradePerformance
from src.backtesting.strategy_runner import (
    CandleSignal,
    StrategyRunner,
)
from src.backtesting.trade_simulator import (
    TradeRequest,
    TradeSimulationResult,
    TradeSimulator,
)


def make_signal(
    *,
    entry_price: float = 100.0,
    exit_price: float = 120.0,
    quantity: float = 1.0,
    strategy: str = "SMC",
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    confidence: float = 80.0,
    duration_minutes: int = 60,
    risk_reward: float = 2.0,
) -> CandleSignal:
    return CandleSignal(
        strategy=strategy,
        symbol=symbol,
        timeframe=timeframe,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        confidence=confidence,
        duration_minutes=duration_minutes,
        risk_reward=risk_reward,
    )


class RecordingSimulator(TradeSimulator):
    def __init__(self) -> None:
        self.requests: list[TradeRequest] = []

    def simulate(
        self,
        trade: TradeRequest,
    ) -> TradeSimulationResult:
        self.requests.append(trade)
        return super().simulate(trade)


class InvalidResultSimulator(TradeSimulator):
    def simulate(  # type: ignore[override]
        self,
        trade: TradeRequest,
    ) -> object:
        return object()


def test_default_simulator_is_created() -> None:
    runner = StrategyRunner()

    assert isinstance(
        runner.simulator,
        TradeSimulator,
    )


def test_accepts_injected_simulator() -> None:
    simulator = RecordingSimulator()
    runner = StrategyRunner(simulator)

    assert runner.simulator is simulator


def test_empty_runner() -> None:
    assert StrategyRunner().run([]) == []


def test_single_profitable_trade() -> None:
    result = StrategyRunner().run(
        [
            make_signal(),
        ]
    )

    assert len(result) == 1
    assert isinstance(
        result[0],
        TradePerformance,
    )

    assert result[0].win is True
    assert result[0].pnl == 19.87


def test_single_losing_trade() -> None:
    result = StrategyRunner().run(
        [
            make_signal(
                entry_price=120.0,
                exit_price=100.0,
            ),
        ]
    )

    assert len(result) == 1
    assert result[0].win is False
    assert result[0].pnl == -20.13


def test_equal_prices_are_loss_after_costs() -> None:
    trade = StrategyRunner().run(
        [
            make_signal(
                entry_price=100.0,
                exit_price=100.0,
            ),
        ]
    )[0]

    assert trade.pnl == -0.12
    assert trade.win is False


def test_zero_quantity_is_not_a_win() -> None:
    trade = StrategyRunner().run(
        [
            make_signal(
                quantity=0.0,
            ),
        ]
    )[0]

    assert trade.pnl == 0.0
    assert trade.win is False


def test_multiple_signals_preserve_input_order() -> None:
    signals = [
        make_signal(
            symbol="BTCUSDT",
            entry_price=100.0,
            exit_price=120.0,
        ),
        make_signal(
            symbol="ETHUSDT",
            entry_price=150.0,
            exit_price=120.0,
        ),
        make_signal(
            symbol="SOLUSDT",
            entry_price=80.0,
            exit_price=100.0,
        ),
    ]

    result = StrategyRunner().run(signals)

    assert [
        trade.symbol
        for trade in result
    ] == [
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
    ]

    assert [
        trade.win
        for trade in result
    ] == [
        True,
        False,
        True,
    ]


def test_trade_information_is_preserved() -> None:
    trade = StrategyRunner().run(
        [
            make_signal(
                strategy="Breaker",
                symbol="ETHUSDT",
                timeframe="15m",
                confidence=91.5,
                duration_minutes=45,
                risk_reward=3.25,
            ),
        ]
    )[0]

    assert trade.strategy == "Breaker"
    assert trade.symbol == "ETHUSDT"
    assert trade.timeframe == "15m"
    assert trade.confidence == 91.5
    assert trade.duration_minutes == 45
    assert trade.risk_reward == 3.25


def test_runner_result_types() -> None:
    trade = StrategyRunner().run(
        [
            make_signal(),
        ]
    )[0]

    assert isinstance(
        trade.pnl,
        float,
    )

    assert isinstance(
        trade.win,
        bool,
    )

    assert isinstance(
        trade.confidence,
        float,
    )

    assert isinstance(
        trade.risk_reward,
        float,
    )


def test_integer_numeric_inputs_are_normalized() -> None:
    signal = CandleSignal(
        strategy="SMC",
        symbol="BTCUSDT",
        timeframe="1h",
        entry_price=100,
        exit_price=120,
        quantity=1,
        confidence=80,
        duration_minutes=60,
        risk_reward=2,
    )

    assert isinstance(
        signal.entry_price,
        float,
    )

    assert isinstance(
        signal.exit_price,
        float,
    )

    assert isinstance(
        signal.quantity,
        float,
    )

    assert isinstance(
        signal.confidence,
        float,
    )

    assert isinstance(
        signal.risk_reward,
        float,
    )


def test_generator_is_consumed_once() -> None:
    consumed: list[int] = []

    def signals():
        for index in range(3):
            consumed.append(index)

            yield make_signal(
                symbol=f"ASSET{index}",
            )

    result = StrategyRunner().run(
        signals(),
    )

    assert consumed == [
        0,
        1,
        2,
    ]

    assert len(result) == 3


def test_injected_simulator_receives_trade_requests() -> None:
    simulator = RecordingSimulator()
    runner = StrategyRunner(simulator)

    runner.run(
        [
            make_signal(
                entry_price=100.0,
                exit_price=110.0,
                quantity=2.0,
            ),
        ]
    )

    assert simulator.requests == [
        TradeRequest(
            entry_price=100.0,
            exit_price=110.0,
            quantity=2.0,
        ),
    ]


def test_rejects_invalid_simulator() -> None:
    with pytest.raises(
        TypeError,
        match=(
            "simulator must be a "
            "TradeSimulator instance"
        ),
    ):
        StrategyRunner(
            object(),  # type: ignore[arg-type]
        )


def test_rejects_invalid_simulator_result() -> None:
    runner = StrategyRunner(
        InvalidResultSimulator(),
    )

    with pytest.raises(
        TypeError,
        match=(
            "simulator must return a "
            "TradeSimulationResult instance"
        ),
    ):
        runner.run(
            [
                make_signal(),
            ]
        )


@pytest.mark.parametrize(
    "signals",
    [
        None,
        1,
        1.5,
        object(),
        "signal",
        b"signal",
    ],
)
def test_rejects_invalid_signal_collection(
    signals: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="signals must be an iterable",
    ):
        StrategyRunner().run(
            signals,  # type: ignore[arg-type]
        )


def test_rejects_invalid_signal_element_with_index() -> None:
    with pytest.raises(
        TypeError,
        match=(
            r"signals\[1\] must be a "
            r"CandleSignal instance"
        ),
    ):
        StrategyRunner().run(
            [
                make_signal(),
                object(),
            ]  # type: ignore[list-item]
        )


@pytest.mark.parametrize(
    "field",
    [
        "symbol",
        "timeframe",
        "strategy",
    ],
)
def test_signal_rejects_non_string_text_fields(
    field: str,
) -> None:
    arguments: dict[str, object] = {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "entry_price": 100.0,
        "exit_price": 120.0,
        "quantity": 1.0,
        "strategy": "SMC",
        "confidence": 80.0,
        "duration_minutes": 60,
        "risk_reward": 2.0,
    }

    arguments[field] = 1

    with pytest.raises(
        TypeError,
        match=rf"{field} must be a string",
    ):
        CandleSignal(
            **arguments,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "symbol",
        "timeframe",
        "strategy",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
    ],
)
def test_signal_rejects_empty_text_fields(
    field: str,
    value: str,
) -> None:
    arguments = {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "entry_price": 100.0,
        "exit_price": 120.0,
        "quantity": 1.0,
        "strategy": "SMC",
        "confidence": 80.0,
        "duration_minutes": 60,
        "risk_reward": 2.0,
    }

    arguments[field] = value

    with pytest.raises(
        ValueError,
        match=rf"{field} must not be empty",
    ):
        CandleSignal(**arguments)


@pytest.mark.parametrize(
    "field",
    [
        "entry_price",
        "exit_price",
        "quantity",
        "confidence",
        "risk_reward",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        True,
        "1",
        None,
        object(),
    ],
)
def test_signal_rejects_non_numeric_values(
    field: str,
    value: object,
) -> None:
    arguments: dict[str, object] = {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "entry_price": 100.0,
        "exit_price": 120.0,
        "quantity": 1.0,
        "strategy": "SMC",
        "confidence": 80.0,
        "duration_minutes": 60,
        "risk_reward": 2.0,
    }

    arguments[field] = value

    with pytest.raises(
        TypeError,
        match=rf"{field} must be a real number",
    ):
        CandleSignal(
            **arguments,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "entry_price",
        "exit_price",
        "quantity",
        "confidence",
        "risk_reward",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_signal_rejects_non_finite_values(
    field: str,
    value: float,
) -> None:
    arguments = {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "entry_price": 100.0,
        "exit_price": 120.0,
        "quantity": 1.0,
        "strategy": "SMC",
        "confidence": 80.0,
        "duration_minutes": 60,
        "risk_reward": 2.0,
    }

    arguments[field] = value

    with pytest.raises(
        ValueError,
        match=rf"{field} must be finite",
    ):
        CandleSignal(**arguments)


@pytest.mark.parametrize(
    "field",
    [
        "entry_price",
        "exit_price",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        0.0,
        -1.0,
    ],
)
def test_signal_rejects_non_positive_prices(
    field: str,
    value: float,
) -> None:
    arguments = {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "entry_price": 100.0,
        "exit_price": 120.0,
        "quantity": 1.0,
        "strategy": "SMC",
        "confidence": 80.0,
        "duration_minutes": 60,
        "risk_reward": 2.0,
    }

    arguments[field] = value

    with pytest.raises(
        ValueError,
        match=rf"{field} must be greater than zero",
    ):
        CandleSignal(**arguments)


def test_signal_rejects_negative_quantity() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "quantity must be greater than "
            "or equal to zero"
        ),
    ):
        make_signal(
            quantity=-0.01,
        )


@pytest.mark.parametrize(
    "confidence",
    [
        -0.01,
        100.01,
    ],
)
def test_signal_rejects_out_of_range_confidence(
    confidence: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "confidence must be between "
            "0.0 and 100.0"
        ),
    ):
        make_signal(
            confidence=confidence,
        )


@pytest.mark.parametrize(
    "duration",
    [
        True,
        1.5,
        "60",
        None,
    ],
)
def test_signal_rejects_non_integer_duration(
    duration: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "duration_minutes must be "
            "an integer"
        ),
    ):
        make_signal(
            duration_minutes=duration,  # type: ignore[arg-type]
        )


def test_signal_rejects_negative_duration() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "duration_minutes must be greater "
            "than or equal to zero"
        ),
    ):
        make_signal(
            duration_minutes=-1,
        )


def test_signal_rejects_negative_risk_reward() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "risk_reward must be greater "
            "than or equal to zero"
        ),
    ):
        make_signal(
            risk_reward=-0.01,
        )


@pytest.mark.parametrize(
    "field",
    [
        "symbol",
        "timeframe",
        "entry_price",
        "exit_price",
        "quantity",
        "strategy",
        "confidence",
        "duration_minutes",
        "risk_reward",
    ],
)
def test_signal_is_immutable(
    field: str,
) -> None:
    signal = make_signal()

    with pytest.raises(
        FrozenInstanceError,
    ):
        setattr(
            signal,
            field,
            None,
        )