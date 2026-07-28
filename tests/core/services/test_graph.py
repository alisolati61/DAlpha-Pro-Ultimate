"""Deterministic validation tests for the local service graph."""

from __future__ import annotations

import pytest

from src.core.lifecycle.service import Service
from src.core.services.errors import (
    DuplicateServiceError,
    MissingServiceDependencyError,
    ServiceDependencyCycleError,
)
from src.core.services.graph import ServiceGraph
from src.core.services.models import ServiceDefinition


class RecordingService(Service):
    def __init__(self, events: list[str], name: str) -> None:
        self.events = events
        self.name = name

    def initialize(self) -> None:
        self.events.append(f"initialize:{self.name}")

    def start(self) -> None:
        self.events.append(f"start:{self.name}")

    def stop(self) -> None:
        self.events.append(f"stop:{self.name}")


def definition(
    service_id: str,
    events: list[str] | None = None,
    dependencies: tuple[str, ...] = (),
) -> ServiceDefinition:
    return ServiceDefinition(
        service_id,
        RecordingService(events if events is not None else [], service_id),
        dependencies,
    )


def resolved_ids(graph: ServiceGraph) -> tuple[str, ...]:
    return tuple(item.service_id for item in graph.resolve())


def test_empty_and_single_service_graphs() -> None:
    assert ServiceGraph().resolve() == ()
    only = definition("only")
    assert ServiceGraph((only,)).resolve() == (only,)


def test_duplicate_ids_are_rejected() -> None:
    with pytest.raises(DuplicateServiceError):
        ServiceGraph((definition("same"), definition("same")))


def test_missing_dependency_is_rejected() -> None:
    with pytest.raises(MissingServiceDependencyError):
        ServiceGraph((definition("worker", dependencies=("missing",)),))


def test_direct_and_indirect_cycles_are_rejected() -> None:
    with pytest.raises(ServiceDependencyCycleError):
        ServiceGraph(
            (
                definition("a", dependencies=("b",)),
                definition("b", dependencies=("a",)),
            )
        )

    with pytest.raises(ServiceDependencyCycleError):
        ServiceGraph(
            (
                definition("a", dependencies=("c",)),
                definition("b", dependencies=("a",)),
                definition("c", dependencies=("b",)),
            )
        )


def test_dependency_chain_and_diamond_order() -> None:
    chain = ServiceGraph(
        (
            definition("leaf", dependencies=("middle",)),
            definition("middle", dependencies=("root",)),
            definition("root"),
        )
    )
    assert resolved_ids(chain) == ("root", "middle", "leaf")

    diamond = ServiceGraph(
        (
            definition("finish", dependencies=("left", "right")),
            definition("right", dependencies=("root",)),
            definition("left", dependencies=("root",)),
            definition("root"),
        )
    )
    assert resolved_ids(diamond) == ("root", "right", "left", "finish")


def test_independent_services_use_registration_order_tie_break() -> None:
    graph = ServiceGraph(
        (
            definition("first"),
            definition("dependent", dependencies=("first",)),
            definition("independent"),
        )
    )

    assert resolved_ids(graph) == (
        "first",
        "dependent",
        "independent",
    )


def test_repeated_resolution_is_identical() -> None:
    graph = ServiceGraph(
        (
            definition("second"),
            definition("first"),
        )
    )

    assert graph.resolve() is graph.resolve()
    assert resolved_ids(graph) == ("second", "first")


def test_graph_construction_invokes_no_lifecycle_method() -> None:
    events: list[str] = []
    definitions = (
        definition("root", events),
        definition("worker", events, ("root",)),
    )

    graph = ServiceGraph(definitions)

    assert resolved_ids(graph) == ("root", "worker")
    assert events == []
