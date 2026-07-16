from __future__ import annotations

from typing import Any

from .mapper import Mapper


class MapperRegistry:

    def __init__(self):

        self._mappers: dict[tuple[type, type], Mapper] = {}

    def register(
        self,
        source: type,
        destination: type,
        mapper: Mapper,
    ) -> None:

        self._mappers[(source, destination)] = mapper

    def resolve(
        self,
        source: type,
        destination: type,
    ) -> Mapper | None:

        return self._mappers.get((source, destination))