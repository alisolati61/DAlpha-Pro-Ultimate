"""Immutable local service graph contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from src.core.services.errors import InvalidServiceDefinitionError

if TYPE_CHECKING:
    from src.core.lifecycle.service import Service

_SERVICE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def _validated_service_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or _SERVICE_ID.fullmatch(value) is None
    ):
        raise InvalidServiceDefinitionError
    return value


class ServiceState(str, Enum):
    """Runtime-owned state for one local service."""

    CREATED = "created"
    INITIALIZED = "initialized"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ServiceDefinition:
    """Stable service identity and its explicit local dependencies."""

    service_id: str
    service: Service
    dependencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        from src.core.lifecycle.service import Service

        service_id = _validated_service_id(self.service_id)
        if not isinstance(self.service, Service):
            raise InvalidServiceDefinitionError
        if not isinstance(self.dependencies, tuple):
            raise InvalidServiceDefinitionError

        dependencies = tuple(
            _validated_service_id(dependency)
            for dependency in self.dependencies
        )
        if service_id in dependencies:
            raise InvalidServiceDefinitionError
        if len(set(dependencies)) != len(dependencies):
            raise InvalidServiceDefinitionError

        object.__setattr__(self, "service_id", service_id)
        object.__setattr__(self, "dependencies", dependencies)


__all__ = (
    "ServiceDefinition",
    "ServiceState",
)
