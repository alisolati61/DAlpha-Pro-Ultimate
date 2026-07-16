from src.domain.value_objects import TimeInForce


def test_gtc():
    assert TimeInForce.GTC.value == "GTC"


def test_ioc():
    assert TimeInForce.IOC.value == "IOC"


def test_fok():
    assert TimeInForce.FOK.value == "FOK"


def test_gtx():
    assert TimeInForce.GTX.value == "GTX"