from src.shared.ids import UUIDGenerator, IdPrefix


def test_generate_order_id():

    gen = UUIDGenerator()

    value = gen.generate(IdPrefix.ORDER)

    assert value.startswith("ORD-")


def test_generate_trade_id():

    gen = UUIDGenerator()

    value = gen.generate(IdPrefix.TRADE)

    assert value.startswith("TRD-")


def test_unique():

    gen = UUIDGenerator()

    a = gen.generate(IdPrefix.EVENT)

    b = gen.generate(IdPrefix.EVENT)

    assert a != b