from src.shared.mapper import Mapper
from src.shared.mapper import MapperRegistry


class IntToStrMapper(Mapper[int, str]):

    def map(self, source: int) -> str:
        return str(source)


def test_registry():

    registry = MapperRegistry()

    mapper = IntToStrMapper()

    registry.register(int, str, mapper)

    resolved = registry.resolve(int, str)

    assert resolved is mapper

    assert resolved.map(123) == "123"