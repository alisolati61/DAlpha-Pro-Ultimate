from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from src.core.lifecycle.service import Service
from src.core.services.errors import (
    DuplicateServiceError,
    LifecycleTransitionError,
)
from src.core.services.graph import ServiceGraph
from src.core.services.models import ServiceDefinition, ServiceState


@dataclass(slots=True)
class _ServiceRecord:
    definition: ServiceDefinition
    state: ServiceState = ServiceState.CREATED
    stop_attempted: bool = False


class LifecycleManager:
    """Canonical owner of local service ordering and lifecycle state."""

    def __init__(
        self,
        definitions: Iterable[ServiceDefinition] = (),
    ) -> None:
        self._records: dict[str, _ServiceRecord] = {}
        self._registration_order: list[str] = []
        self._resolved: tuple[ServiceDefinition, ...] | None = None
        self._owned_ids: list[str] = []
        self._initialized = False
        self._started = False
        self._stopped = False

        for definition in definitions:
            self.register(definition)

    @property
    def definitions(self) -> tuple[ServiceDefinition, ...]:
        return tuple(
            self._records[service_id].definition
            for service_id in self._registration_order
        )

    def register(
        self,
        definition_or_id: ServiceDefinition | str,
        service: Service | None = None,
        dependencies: tuple[str, ...] = (),
    ) -> None:
        """Register an immutable definition or explicit ID/service pair."""

        if self._resolved is not None or self._initialized:
            raise LifecycleTransitionError

        definition = (
            definition_or_id
            if isinstance(definition_or_id, ServiceDefinition)
            else ServiceDefinition(
                service_id=definition_or_id,
                service=service,  # type: ignore[arg-type]
                dependencies=dependencies,
            )
        )
        if definition.service_id in self._records:
            raise DuplicateServiceError

        self._records[definition.service_id] = _ServiceRecord(definition)
        self._registration_order.append(definition.service_id)

    def resolve(self) -> tuple[ServiceDefinition, ...]:
        """Validate once and return deterministic dependency order."""

        if self._resolved is None:
            self._resolved = ServiceGraph(self.definitions).resolve()
        return self._resolved

    def initialize(self) -> None:
        if self._initialized or self._started or self._stopped:
            raise LifecycleTransitionError

        for definition in self.resolve():
            record = self._records[definition.service_id]
            if record.state is not ServiceState.CREATED:
                raise LifecycleTransitionError
            try:
                definition.service.initialize()
            except BaseException:
                record.state = ServiceState.FAILED
                raise
            record.state = ServiceState.INITIALIZED
            self._owned_ids.append(definition.service_id)

        self._initialized = True

    def start(self) -> None:
        if not self._initialized or self._started or self._stopped:
            raise LifecycleTransitionError

        for definition in self.resolve():
            record = self._records[definition.service_id]
            if record.state is not ServiceState.INITIALIZED:
                raise LifecycleTransitionError
            if any(
                self._records[dependency].state
                is not ServiceState.RUNNING
                for dependency in definition.dependencies
            ):
                raise LifecycleTransitionError
            try:
                definition.service.start()
            except BaseException:
                record.state = ServiceState.FAILED
                raise
            record.state = ServiceState.RUNNING

        self._started = True

    def stop(self) -> None:
        if self._stopped:
            return

        errors: list[BaseException] = []
        for service_id in reversed(self._owned_ids):
            record = self._records[service_id]
            if record.stop_attempted:
                continue
            record.stop_attempted = True
            try:
                record.definition.service.stop()
            except BaseException as error:
                record.state = ServiceState.FAILED
                errors.append(error)
            else:
                record.state = ServiceState.STOPPED

        self._stopped = True
        self._started = False
        if errors:
            raise BaseExceptionGroup(
                "Local service shutdown failed.",
                errors,
            )

    def state_of(self, service_id: str) -> ServiceState:
        """Return observable state without exposing service internals."""

        try:
            return self._records[service_id].state
        except (KeyError, TypeError) as error:
            raise LifecycleTransitionError from error
