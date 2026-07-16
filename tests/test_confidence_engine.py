from src.decision import ConfidenceEngine


def test_confidence_normal():

    assert ConfidenceEngine.calculate(80) == 0.80


def test_confidence_maximum():

    assert ConfidenceEngine.calculate(150) == 1.00


def test_confidence_minimum():

    assert ConfidenceEngine.calculate(-10) == 0.00