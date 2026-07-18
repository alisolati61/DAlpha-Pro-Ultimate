from src.data.data_validator import (
    DataValidator,
    ValidationResult,
)


def valid_candle():

    return [
        [
            1,
            100,
            110,
            90,
            105,
            1000,
        ]
    ]


def test_valid():

    validator = DataValidator()

    result = validator.validate(
        valid_candle(),
    )

    assert isinstance(
        result,
        ValidationResult,
    )

    assert result.valid


def test_empty():

    validator = DataValidator()

    result = validator.validate([])

    assert result.valid is False


def test_invalid_length():

    validator = DataValidator()

    result = validator.validate(
        [
            [1, 2, 3]
        ]
    )

    assert result.valid is False


def test_high_low():

    validator = DataValidator()

    result = validator.validate(
        [
            [
                1,
                100,
                90,
                110,
                100,
                100,
            ]
        ]
    )

    assert result.valid is False


def test_open_outside():

    validator = DataValidator()

    result = validator.validate(
        [
            [
                1,
                200,
                110,
                90,
                100,
                100,
            ]
        ]
    )

    assert result.valid is False


def test_close_outside():

    validator = DataValidator()

    result = validator.validate(
        [
            [
                1,
                100,
                110,
                90,
                200,
                100,
            ]
        ]
    )

    assert result.valid is False


def test_result_types():

    validator = DataValidator()

    result = validator.validate(
        valid_candle(),
    )

    assert isinstance(
        result.valid,
        bool,
    )

    assert isinstance(
        result.reason,
        str,
    )