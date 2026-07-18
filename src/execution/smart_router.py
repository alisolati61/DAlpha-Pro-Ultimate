from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping


class ExecutionRoute(str, Enum):
    """
    Supported execution routes.
    """

    PAPER = "paper"
    PRIMARY = "primary"
    SECONDARY = "secondary"


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    """
    A candidate execution route.
    """

    name: str
    available: bool = True
    priority: int = 0


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """
    Result of route selection.
    """

    route: str
    reason: str


class SmartRouter:
    """
    Selects the best available execution route.

    Routing rules:
    1. Explicitly requested route wins if available.
    2. Otherwise, available routes are sorted by priority.
    3. If no route is available, execution is rejected.
    """

    def __init__(
        self,
        routes: Mapping[
            str,
            Callable[..., object],
        ] | None = None,
    ) -> None:

        self._routes = dict(
            routes or {},
        )

    def register(
        self,
        name: str,
        executor: Callable[..., object],
    ) -> None:

        self._validate_name(
            name,
        )

        if not callable(
            executor,
        ):

            raise TypeError(
                "executor must be callable."
            )

        self._routes[name] = executor

    def unregister(
        self,
        name: str,
    ) -> None:

        self._validate_name(
            name,
        )

        self._routes.pop(
            name,
            None,
        )

    def has_route(
        self,
        name: str,
    ) -> bool:

        self._validate_name(
            name,
        )

        return name in self._routes

    def available_routes(
        self,
    ) -> list[str]:

        return list(
            self._routes.keys(),
        )

    def route(
        self,
        candidates: list[RouteCandidate],
        preferred_route: str | None = None,
    ) -> RoutingDecision:

        if not candidates:

            raise ValueError(
                "At least one route candidate is required."
            )

        available = [
            candidate
            for candidate in candidates
            if candidate.available
        ]

        if preferred_route is not None:

            self._validate_name(
                preferred_route,
            )

            for candidate in available:

                if candidate.name == preferred_route:

                    return RoutingDecision(
                        route=candidate.name,
                        reason=(
                            "Preferred route selected."
                        ),
                    )

        if not available:

            raise RuntimeError(
                "No available execution route."
            )

        selected = max(
            available,
            key=lambda candidate: candidate.priority,
        )

        return RoutingDecision(
            route=selected.name,
            reason=(
                "Highest-priority available "
                "route selected."
            ),
        )

    def execute(
        self,
        candidates: list[RouteCandidate],
        *,
        preferred_route: str | None = None,
        args: tuple[object, ...] = (),
        kwargs: dict[str, object] | None = None,
    ) -> object:

        decision = self.route(
            candidates,
            preferred_route=preferred_route,
        )

        executor = self._routes.get(
            decision.route,
        )

        if executor is None:

            raise RuntimeError(
                f"Route '{decision.route}' "
                "is not registered."
            )

        return executor(
            *args,
            **(kwargs or {}),
        )

    @staticmethod
    def _validate_name(
        name: str,
    ) -> str:

        if not isinstance(
            name,
            str,
        ):

            raise TypeError(
                "route name must be a string."
            )

        name = name.strip()

        if not name:

            raise ValueError(
                "route name cannot be empty."
            )

        return name