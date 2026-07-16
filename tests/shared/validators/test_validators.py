from src.shared.validators import ValidationResult


def test_empty_result():

    result = ValidationResult()

    assert result.is_valid


def test_add_error():

    result = ValidationResult()

    result.add("price", "must be positive")

    assert not result.is_valid

    assert len(result.errors) == 1

    assert result.errors[0].field == "price"

    assert result.errors[0].message == "must be positive"