"""High-level coordination for the execution engine.

The manager preserves the historical contract:

- valid requests are delegated exactly once to ``ExecutionEngine.execute``;
- ``True`` becomes ``Execution completed.``;
- ``False`` becomes ``Execution rejected.``;
- engine exceptions propagate unchanged.

The engine must return an actual ``bool``. Truthy or falsy substitutes are
rejected because they make execution outcomes ambiguous.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from src.execution.execution_engine import (
    ExecutionEngine,
    ExecutionRequest,
)

_COMPLETED_MESSAGE = "Execution completed."
_REJECTED_MESSAGE = "Execution rejected."


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Immutable standardized result returned by the coordinator."""

    success: bool
    message: str

    @property
    def rejected(self) -> bool:
        """Return whether execution was rejected."""

        return not self.success

    def __bool__(self) -> bool:
        """Use execution success as the result truth value."""

        return self.success


class ExecutionManager:
    """Validate requests and coordinate high-level execution."""

    __slots__ = ("engine",)

    def __init__(
        self,
        engine: ExecutionEngine,
    ) -> None:
        if not isinstance(
            engine,
            ExecutionEngine,
        ):
            raise TypeError(
                "engine must be an ExecutionEngine."
            )

        self.engine = engine

    @staticmethod
    def _validate_request(
        request: object,
    ) -> ExecutionRequest:
        if not isinstance(
            request,
            ExecutionRequest,
        ):
            raise TypeError(
                "request must be an ExecutionRequest."
            )

        return request

    @staticmethod
    def _result_from_success(
        success: object,
    ) -> ExecutionResult:
        if type(success) is not bool:
            raise TypeError(
                "engine.execute must return a bool."
            )

        if success:
            return ExecutionResult(
                success=True,
                message=_COMPLETED_MESSAGE,
            )

        return ExecutionResult(
            success=False,
            message=_REJECTED_MESSAGE,
        )

    @staticmethod
    def _normalize_requests(
        requests: object,
    ) -> tuple[ExecutionRequest, ...]:
        if (
            isinstance(
                requests,
                (
                    str,
                    bytes,
                    bytearray,
                ),
            )
            or not isinstance(
                requests,
                Iterable,
            )
        ):
            raise TypeError(
                "requests must be an iterable "
                "of ExecutionRequest objects."
            )

        return tuple(
            ExecutionManager._validate_request(
                request
            )
            for request in requests
        )

    def execute(
        self,
        request: ExecutionRequest,
    ) -> ExecutionResult:
        """Execute one validated request and standardize its result."""

        validated_request = self._validate_request(
            request
        )
        success = self.engine.execute(
            validated_request
        )

        return self._result_from_success(
            success
        )

    def execute_many(
        self,
        requests: Iterable[ExecutionRequest],
    ) -> list[ExecutionResult]:
        """Execute multiple requests in input order.

        Every request type is validated before the first engine call. Engine
        exceptions still propagate and stop processing at the failing request.
        """

        validated_requests = (
            self._normalize_requests(
                requests
            )
        )

        return [
            self.execute(request)
            for request in validated_requests
        ]

    def iter_execute(
        self,
        requests: Iterable[ExecutionRequest],
    ) -> Iterator[ExecutionResult]:
        """Lazily execute validated requests in input order.

        The iterable and all request types are validated before yielding the
        first result, preventing late type surprises after partial execution.
        """

        validated_requests = (
            self._normalize_requests(
                requests
            )
        )

        for request in validated_requests:
            yield self.execute(request)


__all__ = (
    "ExecutionManager",
    "ExecutionResult",
)