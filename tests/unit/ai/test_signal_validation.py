from src.ai.signal_validation import (
    SignalValidationEngine,
    ValidationResult,
)


def test_valid_signal():

    engine = SignalValidationEngine()

    scores = {
        "trend": 15,
        "smc": 20,
        "orderflow": 18,
        "risk": 12,
    }

    result = engine.validate(scores)

    assert isinstance(result, ValidationResult)

    assert result.valid is True

    assert result.failed_checks == []

    assert result.passed_checks == 4

    assert result.reason == "Signal validated"

    assert result.score > 0

    assert result.confidence > 0


def test_invalid_signal():

    engine = SignalValidationEngine()

    scores = {
        "trend": 5,
        "smc": 20,
        "orderflow": 8,
        "risk": 3,
    }

    result = engine.validate(scores)

    assert result.valid is False

    assert "trend" in result.failed_checks

    assert "orderflow" in result.failed_checks

    assert "risk" in result.failed_checks

    assert result.passed_checks == 1

    assert result.reason.startswith("Missing confirmation")


def test_missing_scores():

    engine = SignalValidationEngine()

    result = engine.validate({})

    assert result.valid is False

    assert len(result.failed_checks) == 4

    assert result.passed_checks == 0


def test_weighted_score_is_capped():

    engine = SignalValidationEngine()

    scores = {
        "trend": 500,
        "smc": 500,
        "orderflow": 500,
        "risk": 500,
    }

    result = engine.validate(scores)

    assert result.valid is True

    assert result.confidence == 100.0


def test_partial_signal():

    engine = SignalValidationEngine()

    scores = {
        "trend": 12,
        "smc": 15,
        "orderflow": 5,
        "risk": 10,
    }

    result = engine.validate(scores)

    assert result.valid is False

    assert result.passed_checks == 3

    assert result.failed_checks == ["orderflow"]


def test_validation_result_types():

    engine = SignalValidationEngine()

    scores = {
        "trend": 15,
        "smc": 15,
        "orderflow": 15,
        "risk": 15,
    }

    result = engine.validate(scores)

    assert isinstance(result.valid, bool)

    assert isinstance(result.confidence, float)

    assert isinstance(result.score, float)

    assert isinstance(result.passed_checks, int)

    assert isinstance(result.failed_checks, list)

    assert isinstance(result.reason, str)