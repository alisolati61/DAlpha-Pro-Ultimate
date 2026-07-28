"""Deterministic validation and resolution of local service dependencies."""

from __future__ import annotations

import heapq
from collections.abc import Iterable

from src.core.services.errors import (
    DuplicateServiceError,
    MissingServiceDependencyError,
    ServiceDependencyCycleError,
)
from src.core.services.models import ServiceDefinition


class ServiceGraph:
    """Immutable graph resolved with registration-order tie-breaking."""

    def __init__(
        self,
        definitions: Iterable[ServiceDefinition] = (),
    ) -> None:
        normalized = tuple(definitions)
        if not all(
            isinstance(definition, ServiceDefinition)
            for definition in normalized
        ):
            from src.core.services.errors import (
                InvalidServiceDefinitionError,
            )

            raise InvalidServiceDefinitionError

        self._definitions = normalized
        self._resolved = self._validate_and_resolve()

    @property
    def definitions(self) -> tuple[ServiceDefinition, ...]:
        return self._definitions

    def resolve(self) -> tuple[ServiceDefinition, ...]:
        """Return the same deterministic topological order each time."""

        return self._resolved

    def _validate_and_resolve(self) -> tuple[ServiceDefinition, ...]:
        by_id: dict[str, ServiceDefinition] = {}
        registration_index: dict[str, int] = {}

        for index, definition in enumerate(self._definitions):
            if definition.service_id in by_id:
                raise DuplicateServiceError
            by_id[definition.service_id] = definition
            registration_index[definition.service_id] = index

        for definition in self._definitions:
            if any(
                dependency not in by_id
                for dependency in definition.dependencies
            ):
                raise MissingServiceDependencyError

        dependency_count = {
            definition.service_id: len(definition.dependencies)
            for definition in self._definitions
        }
        dependents: dict[str, list[str]] = {
            service_id: []
            for service_id in by_id
        }
        for definition in self._definitions:
            for dependency in definition.dependencies:
                dependents[dependency].append(definition.service_id)

        ready = [
            (registration_index[service_id], service_id)
            for service_id, count in dependency_count.items()
            if count == 0
        ]
        heapq.heapify(ready)
        resolved: list[ServiceDefinition] = []

        while ready:
            _, service_id = heapq.heappop(ready)
            resolved.append(by_id[service_id])
            for dependent in dependents[service_id]:
                dependency_count[dependent] -= 1
                if dependency_count[dependent] == 0:
                    heapq.heappush(
                        ready,
                        (registration_index[dependent], dependent),
                    )

        if len(resolved) != len(self._definitions):
            raise ServiceDependencyCycleError

        return tuple(resolved)


__all__ = ("ServiceGraph",)
