from src.decision.confidence_aggregator import (
    ConfidenceAggregator,
)


def test_high_confidence():

    result = ConfidenceAggregator().aggregate(
        [90, 80, 85]
    )

    assert result.passed
    assert result.confidence > 80


def test_low_confidence():

    result = ConfidenceAggregator().aggregate(
        [30, 40, 50]
    )

    assert not result.passed


def test_empty():

    result = ConfidenceAggregator().aggregate([])

    assert result.confidence == 0
    assert not result.passed