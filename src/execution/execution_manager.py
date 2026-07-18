from __future__ import annotations

from dataclasses import dataclass

from src.execution.execution_engine import (
    ExecutionEngine,
    ExecutionRequest,
)


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """
    Standardized result returned by the execution coordinator.
    """

    success: bool
    message: str


class ExecutionManager:
    """
    High-level execution coordinator.

    Pipeline:

        Signal
            ↓
        Decision
            ↓
        Risk
            ↓
        ExecutionEngine
            ↓
        Exchange
    """

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

    def execute(
        self,
        request: ExecutionRequest,
    ) -> ExecutionResult:

        if not isinstance(
            request,
            ExecutionRequest,
        ):

            raise TypeError(
                "request must be an ExecutionRequest."
            )

        success = self.engine.execute(
            request,
        )

        if success:

            return ExecutionResult(
                success=True,
                message="Execution completed.",
            )

        return ExecutionResult(
            success=False,
            message="Execution rejected.",
        )