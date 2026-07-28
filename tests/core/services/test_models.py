"""Contract tests for local service definitions and states."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.core.lifecycle.service import Service
from src.core.services.errors import InvalidServiceDefinitionError
from src.core.services.models import ServiceDefinition, ServiceState


class NoOpService(Service):
    def initialize(self) -> None:
        return None

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None


def test_definition_is_immutable_and_preserves_service() -> None:
    service = NoOpService()
    definition = ServiceDefinition(
        "worker",
        service,
        ("database",),
    )

    assert definition.service is service
    assert definition.dependencies == ("database",)

    with pytest.raises(FrozenInstanceError):
        definition.service_id = "other"  # type: ignore[misc]


@pytest.mark.parametrize(
    "service_id",
    ["", " ", " leading", "trailing ", ".hidden", "bad/id", "bad:id"],
)
def test_service_id_must_be_stable_and_non_empty(
    service_id: str,
) -> None:
    with pytest.raises(InvalidServiceDefinitionError):
        ServiceDefinition(service_id, NoOpService())


def test_service_and_dependencies_are_validated() -> None:
    with pytest.raises(InvalidServiceDefinitionError):
        ServiceDefinition("worker", object())  # type: ignore[arg-type]
    with pytest.raises(InvalidServiceDefinitionError):
        ServiceDefinition(
            "worker",
            NoOpService(),
            ["database"],  # type: ignore[arg-type]
        )


def test_self_and_duplicate_dependencies_are_rejected() -> None:
    with pytest.raises(InvalidServiceDefinitionError):
        ServiceDefinition("worker", NoOpService(), ("worker",))
    with pytest.raises(InvalidServiceDefinitionError):
        ServiceDefinition(
            "worker",
            NoOpService(),
            ("database", "database"),
        )


def test_service_states_are_explicit_and_stable() -> None:
    assert tuple(state.value for state in ServiceState) == (
        "created",
        "initialized",
        "running",
        "stopped",
        "failed",
    )
