"""Tests for deterministic and thread-safe smart routing."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError

import pytest

from src.execution.smart_router import (
    ExecutionRoute,
    RouteCandidate,
    RoutingDecision,
    SmartRouter,
)


def candidate(
    name: str = "primary",
    *,
    available: bool = True,
    priority: int = 0,
) -> RouteCandidate:
    return RouteCandidate(
        name=name,
        available=available,
        priority=priority,
    )


def test_execution_route_values() -> None:
    assert ExecutionRoute.PAPER.value == "paper"
    assert ExecutionRoute.PRIMARY.value == "primary"
    assert ExecutionRoute.SECONDARY.value == "secondary"


def test_route_candidate_is_immutable() -> None:
    value = candidate()

    with pytest.raises(FrozenInstanceError):
        value.priority = 10  # type: ignore[misc]


def test_routing_decision_is_immutable() -> None:
    value = RoutingDecision(
        route="primary",
        reason="Selected.",
    )

    with pytest.raises(FrozenInstanceError):
        value.route = "other"  # type: ignore[misc]


def test_empty_router_state() -> None:
    router = SmartRouter()

    assert router.available_routes() == []
    assert len(router) == 0
    assert bool(router) is False


def test_constructor_registers_routes() -> None:
    executor = lambda: "ok"
    router = SmartRouter(
        {
            "primary": executor,
        }
    )

    assert router.has_route("primary") is True
    assert router.available_routes() == ["primary"]
    assert len(router) == 1


def test_constructor_normalizes_route_names() -> None:
    router = SmartRouter(
        {
            "  primary  ": lambda: "ok",
        }
    )

    assert router.available_routes() == ["primary"]
    assert router.has_route(" primary ") is True


@pytest.mark.parametrize(
    "routes",
    [
        [],
        (),
        "routes",
        1,
        True,
        object(),
    ],
)
def test_constructor_rejects_non_mapping(
    routes: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="routes must be a mapping or None",
    ):
        SmartRouter(
            routes=routes,  # type: ignore[arg-type]
        )


def test_constructor_rejects_invalid_executor() -> None:
    with pytest.raises(
        TypeError,
        match="executor must be callable",
    ):
        SmartRouter(
            {
                "primary": "invalid",  # type: ignore[dict-item]
            }
        )


def test_register_route() -> None:
    router = SmartRouter()
    executor = lambda: "ok"

    result = router.register(
        "primary",
        executor,
    )

    assert result is None
    assert router.has_route("primary") is True


def test_register_normalizes_name() -> None:
    router = SmartRouter()

    router.register(
        "  primary  ",
        lambda: "ok",
    )

    assert router.available_routes() == ["primary"]
    assert router.has_route(" primary ") is True


def test_register_replaces_executor() -> None:
    router = SmartRouter(
        {
            "primary": lambda: "first",
        }
    )

    router.register(
        "primary",
        lambda: "second",
    )

    assert router.execute(
        [candidate()]
    ) == "second"
    assert len(router) == 1


def test_unregister_route() -> None:
    router = SmartRouter(
        {
            "primary": lambda: "ok",
        }
    )

    result = router.unregister(
        " primary "
    )

    assert result is None
    assert router.has_route("primary") is False


def test_unregister_missing_is_safe() -> None:
    router = SmartRouter()

    assert router.unregister("missing") is None
    assert router.available_routes() == []


def test_clear_routes() -> None:
    router = SmartRouter(
        {
            "primary": lambda: "ok",
            "secondary": lambda: "ok",
        }
    )

    result = router.clear()

    assert result is None
    assert len(router) == 0


def test_available_routes_returns_new_list() -> None:
    router = SmartRouter(
        {
            "primary": lambda: "ok",
        }
    )

    routes = router.available_routes()
    routes.clear()

    assert router.available_routes() == ["primary"]


@pytest.mark.parametrize(
    "name",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_empty_route_name_rejected(
    name: str,
) -> None:
    router = SmartRouter()

    with pytest.raises(
        ValueError,
        match="route name cannot be empty",
    ):
        router.register(
            name,
            lambda: None,
        )


@pytest.mark.parametrize(
    "name",
    [
        None,
        1,
        True,
        [],
        {},
        object(),
    ],
)
def test_invalid_route_name_type_rejected(
    name: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="route name must be a string",
    ):
        SmartRouter().has_route(
            name  # type: ignore[arg-type]
        )


def test_route_name_length_is_bounded() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "route name must not exceed "
            "200 characters"
        ),
    ):
        SmartRouter().register(
            "x" * 201,
            lambda: None,
        )


@pytest.mark.parametrize(
    "executor",
    [
        None,
        1,
        True,
        "callable",
        [],
        {},
        object(),
    ],
)
def test_non_callable_executor_rejected(
    executor: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="executor must be callable",
    ):
        SmartRouter().register(
            "primary",
            executor,  # type: ignore[arg-type]
        )


def test_preferred_route_is_selected() -> None:
    decision = SmartRouter().route(
        [
            candidate(
                "primary",
                priority=10,
            ),
            candidate(
                "secondary",
                priority=100,
            ),
        ],
        preferred_route="primary",
    )

    assert decision == RoutingDecision(
        route="primary",
        reason="Preferred route selected.",
    )


def test_preferred_route_is_normalized() -> None:
    decision = SmartRouter().route(
        [
            candidate(" primary "),
        ],
        preferred_route=" primary ",
    )

    assert decision.route == "primary"


def test_unavailable_preferred_route_falls_back() -> None:
    decision = SmartRouter().route(
        [
            candidate(
                "primary",
                available=False,
                priority=100,
            ),
            candidate(
                "secondary",
                priority=10,
            ),
        ],
        preferred_route="primary",
    )

    assert decision.route == "secondary"


def test_missing_preferred_route_falls_back() -> None:
    decision = SmartRouter().route(
        [
            candidate(
                "primary",
                priority=10,
            ),
        ],
        preferred_route="missing",
    )

    assert decision.route == "primary"


def test_highest_priority_is_selected() -> None:
    decision = SmartRouter().route(
        [
            candidate(
                "primary",
                priority=10,
            ),
            candidate(
                "secondary",
                priority=100,
            ),
        ]
    )

    assert decision == RoutingDecision(
        route="secondary",
        reason=(
            "Highest-priority available "
            "route selected."
        ),
    )


def test_equal_priority_preserves_first_candidate() -> None:
    decision = SmartRouter().route(
        [
            candidate(
                "first",
                priority=10,
            ),
            candidate(
                "second",
                priority=10,
            ),
        ]
    )

    assert decision.route == "first"


def test_negative_priorities_are_supported() -> None:
    decision = SmartRouter().route(
        [
            candidate(
                "lower",
                priority=-10,
            ),
            candidate(
                "higher",
                priority=-1,
            ),
        ]
    )

    assert decision.route == "higher"


def test_unavailable_candidates_are_ignored() -> None:
    decision = SmartRouter().route(
        [
            candidate(
                "primary",
                available=False,
                priority=100,
            ),
            candidate(
                "secondary",
                priority=1,
            ),
        ]
    )

    assert decision.route == "secondary"


def test_route_accepts_generator() -> None:
    decision = SmartRouter().route(
        candidate(
            name,
            priority=index,
        )
        for index, name in enumerate(
            [
                "primary",
                "secondary",
            ]
        )
    )

    assert decision.route == "secondary"


@pytest.mark.parametrize(
    "candidates",
    [
        None,
        1,
        True,
        object(),
        "primary",
        b"primary",
        bytearray(b"primary"),
    ],
)
def test_invalid_candidates_container_rejected(
    candidates: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="candidates must be an iterable",
    ):
        SmartRouter().route(
            candidates  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "candidates",
    [
        [],
        (),
    ],
)
def test_empty_candidates_rejected(
    candidates: object,
) -> None:
    with pytest.raises(
        ValueError,
        match="At least one route candidate",
    ):
        SmartRouter().route(
            candidates  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "invalid_candidate",
    [
        None,
        1,
        True,
        "primary",
        {},
        object(),
    ],
)
def test_invalid_candidate_type_rejected(
    invalid_candidate: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="candidate must be a RouteCandidate",
    ):
        SmartRouter().route(
            [
                invalid_candidate,  # type: ignore[list-item]
            ]
        )


@pytest.mark.parametrize(
    "name",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_candidate_empty_name_rejected(
    name: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="route name cannot be empty",
    ):
        SmartRouter().route(
            [
                candidate(name),
            ]
        )


@pytest.mark.parametrize(
    "name",
    [
        None,
        1,
        True,
        object(),
    ],
)
def test_candidate_invalid_name_type_rejected(
    name: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="route name must be a string",
    ):
        SmartRouter().route(
            [
                RouteCandidate(
                    name=name,  # type: ignore[arg-type]
                ),
            ]
        )


@pytest.mark.parametrize(
    "available",
    [
        0,
        1,
        None,
        "yes",
        object(),
    ],
)
def test_candidate_invalid_available_rejected(
    available: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="candidate available must be a bool",
    ):
        SmartRouter().route(
            [
                RouteCandidate(
                    name="primary",
                    available=available,  # type: ignore[arg-type]
                ),
            ]
        )


@pytest.mark.parametrize(
    "priority",
    [
        True,
        False,
        1.5,
        "10",
        None,
        object(),
    ],
)
def test_candidate_invalid_priority_rejected(
    priority: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "candidate priority must "
            "be an integer"
        ),
    ):
        SmartRouter().route(
            [
                RouteCandidate(
                    name="primary",
                    priority=priority,  # type: ignore[arg-type]
                ),
            ]
        )


def test_no_available_route_rejected() -> None:
    with pytest.raises(
        RuntimeError,
        match="No available execution route",
    ):
        SmartRouter().route(
            [
                candidate(
                    "primary",
                    available=False,
                ),
            ]
        )


def test_execute_calls_selected_executor() -> None:
    router = SmartRouter(
        {
            "primary": lambda value: value * 2,
        }
    )

    assert router.execute(
        [
            candidate("primary"),
        ],
        args=(5,),
    ) == 10


def test_execute_passes_keyword_arguments() -> None:
    router = SmartRouter(
        {
            "primary": (
                lambda *, value: value + 1
            ),
        }
    )

    assert router.execute(
        [
            candidate("primary"),
        ],
        kwargs={
            "value": 4,
        },
    ) == 5


def test_execute_accepts_list_args() -> None:
    router = SmartRouter(
        {
            "primary": (
                lambda left, right: left + right
            ),
        }
    )

    assert router.execute(
        [
            candidate("primary"),
        ],
        args=[2, 3],
    ) == 5


def test_execute_uses_preferred_route() -> None:
    router = SmartRouter(
        {
            "primary": lambda: "primary",
            "secondary": lambda: "secondary",
        }
    )

    result = router.execute(
        [
            candidate(
                "primary",
                priority=1,
            ),
            candidate(
                "secondary",
                priority=100,
            ),
        ],
        preferred_route="primary",
    )

    assert result == "primary"


def test_execute_unregistered_route_rejected() -> None:
    with pytest.raises(
        RuntimeError,
        match="Route 'primary' is not registered",
    ):
        SmartRouter().execute(
            [
                candidate("primary"),
            ]
        )


@pytest.mark.parametrize(
    "args",
    [
        None,
        1,
        True,
        object(),
        "args",
        b"args",
        bytearray(b"args"),
    ],
)
def test_invalid_args_rejected(
    args: object,
) -> None:
    router = SmartRouter(
        {
            "primary": lambda: None,
        }
    )

    with pytest.raises(
        TypeError,
        match="args must be an iterable",
    ):
        router.execute(
            [
                candidate("primary"),
            ],
            args=args,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        1,
        True,
        "kwargs",
        [],
        object(),
    ],
)
def test_invalid_kwargs_rejected(
    kwargs: object,
) -> None:
    router = SmartRouter(
        {
            "primary": lambda: None,
        }
    )

    with pytest.raises(
        TypeError,
        match="kwargs must be a mapping or None",
    ):
        router.execute(
            [
                candidate("primary"),
            ],
            kwargs=kwargs,  # type: ignore[arg-type]
        )


def test_non_string_kwargs_key_rejected() -> None:
    router = SmartRouter(
        {
            "primary": lambda: None,
        }
    )

    with pytest.raises(
        TypeError,
        match="kwargs keys must be strings",
    ):
        router.execute(
            [
                candidate("primary"),
            ],
            kwargs={
                1: "value",  # type: ignore[dict-item]
            },
        )


def test_executor_exception_propagates() -> None:
    def executor() -> None:
        raise LookupError("exchange unavailable")

    router = SmartRouter(
        {
            "primary": executor,
        }
    )

    with pytest.raises(
        LookupError,
        match="exchange unavailable",
    ):
        router.execute(
            [
                candidate("primary"),
            ]
        )


def test_concurrent_registration_is_safe() -> None:
    router = SmartRouter()

    def register(index: int) -> None:
        router.register(
            f"route-{index}",
            lambda: index,
        )

    with ThreadPoolExecutor(
        max_workers=16,
    ) as executor:
        list(
            executor.map(
                register,
                range(500),
            )
        )

    assert len(router) == 500
    assert len(
        set(router.available_routes())
    ) == 500