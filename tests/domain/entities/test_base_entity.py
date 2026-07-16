from dataclasses import dataclass
from uuid import uuid4

from src.domain.entities import BaseEntity


@dataclass(eq=False)
class FakeEntity(BaseEntity):
    pass


def test_entity_equality():

    entity_id = uuid4()

    a = FakeEntity(entity_id)

    b = FakeEntity(entity_id)

    assert a == b


def test_entity_hash():

    entity = FakeEntity(uuid4())

    assert hash(entity)