"""Tests for validated rolling walk-forward window generation."""

from dataclasses import FrozenInstanceError
from math import inf, nan

import pytest

from src.backtesting.walk_forward import (
    WalkForward,
    WalkForwardWindow,
)


def test_empty_data_returns_no_windows() -> None:
    assert WalkForward().generate([]) == []


def test_default_window_generation() -> None:
    windows = WalkForward().generate(
        list(range(100)),
    )

    assert windows == [
        WalkForwardWindow(
            train_start=0,
            train_end=70,
            test_start=70,
            test_end=90,
        ),
        WalkForwardWindow(
            train_start=10,
            train_end=80,
            test_start=80,
            test_end=100,
        ),
    ]


def test_train_range_ends_where_test_range_starts() -> None:
    windows = WalkForward().generate(
        list(range(100)),
    )

    assert all(
        window.train_end == window.test_start
        for window in windows
    )


def test_custom_sizes() -> None:
    windows = WalkForward().generate(
        list(range(500)),
        train_size=0.6,
        test_size=0.2,
        step=0.2,
    )

    assert windows == [
        WalkForwardWindow(
            train_start=0,
            train_end=300,
            test_start=300,
            test_end=400,
        ),
        WalkForwardWindow(
            train_start=100,
            train_end=400,
            test_start=400,
            test_end=500,
        ),
    ]


def test_multiple_windows_are_generated_for_large_dataset() -> None:
    windows = WalkForward().generate(
        list(range(1000)),
    )

    assert len(windows) == 2


def test_only_full_windows_are_returned() -> None:
    windows = WalkForward().generate(
        list(range(11)),
        train_size=0.5,
        test_size=0.3,
        step=0.2,
    )

    assert windows == [
        WalkForwardWindow(0, 5, 5, 8),
        WalkForwardWindow(2, 7, 7, 10),
    ]

    assert all(
        window.test_end <= 11
        for window in windows
    )


def test_window_counts_use_floor() -> None:
    windows = WalkForward().generate(
        list(range(9)),
        train_size=0.5,
        test_size=0.25,
        step=0.25,
    )

    assert windows[0].train_length == 4
    assert windows[0].test_length == 2

    assert [
        window.train_start
        for window in windows
    ] == [0, 2]


def test_small_positive_fractions_are_clamped_to_one_observation() -> None:
    windows = WalkForward().generate(
        [1, 2, 3],
        train_size=0.01,
        test_size=0.01,
        step=0.01,
    )

    assert windows == [
        WalkForwardWindow(0, 1, 1, 2),
        WalkForwardWindow(1, 2, 2, 3),
    ]


def test_single_observation_cannot_form_complete_window() -> None:
    windows = WalkForward().generate(
        [1],
        train_size=0.5,
        test_size=0.5,
        step=0.5,
    )

    assert windows == []


def test_two_observations_can_form_minimum_window() -> None:
    windows = WalkForward().generate(
        [1, 2],
        train_size=0.5,
        test_size=0.5,
        step=0.5,
    )

    assert windows == [
        WalkForwardWindow(0, 1, 1, 2),
    ]


def test_exact_full_dataset_window() -> None:
    windows = WalkForward().generate(
        list(range(10)),
        train_size=0.8,
        test_size=0.2,
        step=0.1,
    )

    assert windows == [
        WalkForwardWindow(0, 8, 8, 10),
    ]


def test_step_controls_start_stride() -> None:
    windows = WalkForward().generate(
        list(range(20)),
        train_size=0.4,
        test_size=0.2,
        step=0.15,
    )

    assert [
        window.train_start
        for window in windows
    ] == [
        0,
        3,
        6,
    ]


def test_input_data_is_not_accessed_by_index() -> None:
    class LengthOnly:
        def __len__(self) -> int:
            return 10

    windows = WalkForward().generate(
        LengthOnly(),  # type: ignore[arg-type]
        train_size=0.5,
        test_size=0.2,
        step=0.2,
    )

    assert windows == [
        WalkForwardWindow(0, 5, 5, 7),
        WalkForwardWindow(2, 7, 7, 9),
    ]


@pytest.mark.parametrize(
    "data",
    [
        None,
        1,
        1.5,
        object(),
        (item for item in range(10)),
        "0123456789",
        b"0123456789",
        bytearray(b"0123456789"),
    ],
)
def test_rejects_invalid_or_unsized_data(
    data: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="data must be a sized sequence",
    ):
        WalkForward().generate(
            data,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "train_size",
        "test_size",
        "step",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        "0.2",
        None,
        object(),
    ],
)
def test_rejects_non_numeric_fraction(
    field: str,
    value: object,
) -> None:
    arguments: dict[str, object] = {
        "data": list(range(100)),
        "train_size": 0.6,
        "test_size": 0.2,
        "step": 0.1,
    }

    arguments[field] = value

    with pytest.raises(
        TypeError,
        match=rf"{field} must be a real number",
    ):
        WalkForward().generate(
            **arguments,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "train_size",
        "test_size",
        "step",
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
def test_rejects_non_finite_fraction(
    field: str,
    value: float,
) -> None:
    arguments = {
        "data": list(range(100)),
        "train_size": 0.6,
        "test_size": 0.2,
        "step": 0.1,
    }

    arguments[field] = value

    with pytest.raises(
        ValueError,
        match=rf"{field} must be finite",
    ):
        WalkForward().generate(**arguments)


@pytest.mark.parametrize(
    "field",
    [
        "train_size",
        "test_size",
        "step",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        -0.1,
        0.0,
        1.01,
    ],
)
def test_rejects_fraction_outside_valid_range(
    field: str,
    value: float,
) -> None:
    arguments = {
        "data": list(range(100)),
        "train_size": 0.6,
        "test_size": 0.2,
        "step": 0.1,
    }

    arguments[field] = value

    with pytest.raises(
        ValueError,
        match=(
            rf"{field} must be between 0.0 exclusive "
            rf"and 1.0 inclusive"
        ),
    ):
        WalkForward().generate(**arguments)


def test_rejects_train_and_test_sum_above_one() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "train_size and test_size "
            "must sum to at most 1.0"
        ),
    ):
        WalkForward().generate(
            list(range(100)),
            train_size=0.8,
            test_size=0.3,
        )


def test_configuration_is_validated_even_for_empty_data() -> None:
    with pytest.raises(
        ValueError,
        match="train_size must be between",
    ):
        WalkForward().generate(
            [],
            train_size=0.0,
        )


def test_window_properties() -> None:
    window = WalkForwardWindow(
        train_start=10,
        train_end=30,
        test_start=30,
        test_end=40,
    )

    assert window.train_length == 20
    assert window.test_length == 10
    assert window.total_length == 30

    assert window.train_slice == slice(10, 30)
    assert window.test_slice == slice(30, 40)


def test_window_slices_select_expected_data() -> None:
    data = list(range(20))

    window = WalkForwardWindow(
        train_start=2,
        train_end=8,
        test_start=8,
        test_end=12,
    )

    assert data[window.train_slice] == list(
        range(2, 8)
    )

    assert data[window.test_slice] == list(
        range(8, 12)
    )


@pytest.mark.parametrize(
    "field",
    [
        "train_start",
        "train_end",
        "test_start",
        "test_end",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        True,
        1.5,
        "1",
        None,
    ],
)
def test_window_rejects_non_integer_index(
    field: str,
    value: object,
) -> None:
    arguments: dict[str, object] = {
        "train_start": 0,
        "train_end": 5,
        "test_start": 5,
        "test_end": 7,
    }

    arguments[field] = value

    with pytest.raises(
        TypeError,
        match=rf"{field} must be an integer",
    ):
        WalkForwardWindow(
            **arguments,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "train_start",
        "train_end",
        "test_start",
        "test_end",
    ],
)
def test_window_rejects_negative_index(
    field: str,
) -> None:
    arguments = {
        "train_start": 0,
        "train_end": 5,
        "test_start": 5,
        "test_end": 7,
    }

    arguments[field] = -1

    with pytest.raises(
        ValueError,
        match=(
            rf"{field} must be greater than "
            rf"or equal to zero"
        ),
    ):
        WalkForwardWindow(**arguments)


@pytest.mark.parametrize(
    (
        "arguments",
        "message",
    ),
    [
        (
            {
                "train_start": 2,
                "train_end": 2,
                "test_start": 2,
                "test_end": 3,
            },
            "train_start must be less than train_end",
        ),
        (
            {
                "train_start": 3,
                "train_end": 2,
                "test_start": 2,
                "test_end": 3,
            },
            "train_start must be less than train_end",
        ),
        (
            {
                "train_start": 0,
                "train_end": 5,
                "test_start": 6,
                "test_end": 8,
            },
            "train_end must equal test_start",
        ),
        (
            {
                "train_start": 0,
                "train_end": 5,
                "test_start": 5,
                "test_end": 5,
            },
            "test_start must be less than test_end",
        ),
        (
            {
                "train_start": 0,
                "train_end": 5,
                "test_start": 5,
                "test_end": 4,
            },
            "test_start must be less than test_end",
        ),
    ],
)
def test_window_rejects_invalid_boundaries(
    arguments: dict[str, int],
    message: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=message,
    ):
        WalkForwardWindow(**arguments)


@pytest.mark.parametrize(
    "field",
    [
        "train_start",
        "train_end",
        "test_start",
        "test_end",
    ],
)
def test_window_is_immutable(
    field: str,
) -> None:
    window = WalkForwardWindow(
        train_start=0,
        train_end=5,
        test_start=5,
        test_end=7,
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        setattr(
            window,
            field,
            0,
        )