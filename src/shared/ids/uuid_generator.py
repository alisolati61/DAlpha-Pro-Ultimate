import uuid

from .generator import IdGenerator
from .prefixes import IdPrefix


class UUIDGenerator(IdGenerator):

    def generate(self, prefix: IdPrefix) -> str:
        return f"{prefix.value}-{uuid.uuid4().hex.upper()}"