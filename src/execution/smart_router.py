"""Deterministic and thread-safe execution-route selection.

Routing rules:

1. An explicitly preferred route wins when its candidate is available.
2. Otherwise, the available candidate with the highest priority is selected.
3. Equal priorities preserve candidate order.
4. Selection is independent from registration; execution additionally requires
   a registered callable for the selected route.

Route names are stripped before storage and comparison. Direct construction of
the immutable data models remains permissive; validation happens at the router
boundary.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import Callable, TypeAlias

Executor: TypeAlias = Callable[..., object]

_MAX_ROUTE_NAME_LENGTH = 200


class ExecutionRoute(str, Enum):
    """Built-in execution-route names."""

    PAPER = "paper"
    PRIMARY = "primary"
    SECONDARY = "secondary"


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    """One route considered during selection."""

    name: str
    available: bool = True
    priority: int = 0


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """Immutable route-selection result."""

    route: str
    reason: str


class SmartRouter:
    """Register executors and select deterministic execution routes."""

    __slots__ = (
        "_lock",
        "_routes",
    )

    def __init__(
        self,
        routes: Mapping[str, Executor] | None = None,
    ) -> None:
        if routes is not None and not isinstance(
            routes,
            Mapping,
        ):
            raise TypeError(
                "routes must be a mapping or None."
            )

        normalized_routes: dict[str, Executor] = {}

        if routes is not None:
            for name, executor in routes.items():
                normalized_name = self._validate_name(
                    name
                )
                normalized_executor = (
                    self._validate_executor(
                        executor
                    )
                )
                normalized_routes[
                    normalized_name
                ] = normalized_executor

        self._lock = RLock()
        self._routes = normalized_routes

    @staticmethod
    def _validate_name(
        name: object,
    ) -> str:
        if not isinstance(name, str):
            raise TypeError(
                "route name must be a string."
            )

        normalized = name.strip()

        if not normalized:
            raise ValueError(
                "route name cannot be empty."
            )

        if len(normalized) > _MAX_ROUTE_NAME_LENGTH:
            raise ValueError(
                "route name must not exceed "
                f"{_MAX_ROUTE_NAME_LENGTH} characters."
            )

        return normalized

    @staticmethod
    def _validate_executor(
        executor: object,
    ) -> Executor:
        if not callable(executor):
            raise TypeError(
                "executor must be callable."
            )

        return executor

    @classmethod
    def _normalize_candidate(
        cls,
        candidate: object,
    ) -> RouteCandidate:
        if not isinstance(
            candidate,
            RouteCandidate,
        ):
            raise TypeError(
                "candidate must be a RouteCandidate."
            )

        name = cls._validate_name(
            candidate.name
        )

        if type(candidate.available) is not bool:
            raise TypeError(
                "candidate available must be a bool."
            )

        if (
            isinstance(candidate.priority, bool)
            or not isinstance(
                candidate.priority,
                int,
            )
        ):
            raise TypeError(
                "candidate priority must be an integer."
            )

        return RouteCandidate(
            name=name,
            available=candidate.available,
            priority=candidate.priority,
        )

    @classmethod
    def _normalize_candidates(
        cls,
        candidates: object,
    ) -> tuple[RouteCandidate, ...]:
        if (
            isinstance(
                candidates,
                (
                    str,
                    bytes,
                    bytearray,
                ),
            )
            or not isinstance(
                candidates,
                Iterable,
            )
        ):
            raise TypeError(
                "candidates must be an iterable "
                "of RouteCandidate objects."
            )

        normalized = tuple(
            cls._normalize_candidate(candidate)
            for candidate in candidates
        )

        if not normalized:
            raise ValueError(
                "At least one route candidate is required."
            )

        return normalized

    @staticmethod
    def _normalize_args(
        args: object,
    ) -> tuple[object, ...]:
        if isinstance(
            args,
            (
                str,
                bytes,
                bytearray,
            ),
        ):
            raise TypeError(
                "args must be an iterable of arguments."
            )

        try:
            return tuple(args)  # type: ignore[arg-type]
        except TypeError as error:
            raise TypeError(
                "args must be an iterable of arguments."
            ) from error

    @staticmethod
    def _normalize_kwargs(
        kwargs: object | None,
    ) -> dict[str, object]:
        if kwargs is None:
            return {}

        if not isinstance(
            kwargs,
            Mapping,
        ):
            raise TypeError(
                "kwargs must be a mapping or None."
            )

        normalized = dict(kwargs)

        if not all(
            isinstance(key, str)
            for key in normalized
        ):
            raise TypeError(
                "kwargs keys must be strings."
            )

        return normalized

    def register(
        self,
        name: str,
        executor: Executor,
    ) -> None:
        """Register or replace one route executor."""

        normalized_name = self._validate_name(
            name
        )
        normalized_executor = (
            self._validate_executor(
                executor
            )
        )

        with self._lock:
            self._routes[
                normalized_name
            ] = normalized_executor

    def unregister(
        self,
        name: str,
    ) -> None:
        """Remove one route; missing routes are ignored."""

        normalized_name = self._validate_name(
            name
        )

        with self._lock:
            self._routes.pop(
                normalized_name,
                None,
            )

    def clear(
        self,
    ) -> None:
        """Remove every registered executor."""

        with self._lock:
            self._routes.clear()

    def has_route(
        self,
        name: str,
    ) -> bool:
        """Return whether a normalized route name is registered."""

        normalized_name = self._validate_name(
            name
        )

        with self._lock:
            return normalized_name in self._routes

    def available_routes(
        self,
    ) -> list[str]:
        """Return an independent insertion-ordered name snapshot."""

        with self._lock:
            return list(
                self._routes.keys()
            )

    def route(
        self,
        candidates: Iterable[RouteCandidate],
        preferred_route: str | None = None,
    ) -> RoutingDecision:
        """Select an available candidate deterministically."""

        normalized_candidates = (
            self._normalize_candidates(
                candidates
            )
        )
        available = tuple(
            candidate
            for candidate in normalized_candidates
            if candidate.available
        )

        if preferred_route is not None:
            preferred = self._validate_name(
                preferred_route
            )

            for candidate in available:
                if candidate.name == preferred:
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
            key=lambda candidate: (
                candidate.priority
            ),
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
        candidates: Iterable[RouteCandidate],
        *,
        preferred_route: str | None = None,
        args: Iterable[object] = (),
        kwargs: Mapping[str, object] | None = None,
    ) -> object:
        """Select a route and invoke its registered executor."""

        normalized_args = self._normalize_args(
            args
        )
        normalized_kwargs = (
            self._normalize_kwargs(
                kwargs
            )
        )
        decision = self.route(
            candidates,
            preferred_route=preferred_route,
        )

        with self._lock:
            executor = self._routes.get(
                decision.route
            )

        if executor is None:
            raise RuntimeError(
                f"Route '{decision.route}' "
                "is not registered."
            )

        return executor(
            *normalized_args,
            **normalized_kwargs,
        )

    def __len__(
        self,
    ) -> int:
        with self._lock:
            return len(self._routes)

    def __bool__(
        self,
    ) -> bool:
        with self._lock:
            return bool(self._routes)


__all__ = (
    "ExecutionRoute",
    "RouteCandidate",
    "RoutingDecision",
    "SmartRouter",
)