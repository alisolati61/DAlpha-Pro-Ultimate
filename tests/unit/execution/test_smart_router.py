from __future__ import annotations

import pytest

from src.execution.smart_router import (
    RouteCandidate,
    RoutingDecision,
    SmartRouter,
)


def test_empty_router_has_no_routes():

    router = SmartRouter()

    assert router.available_routes() == []


def test_register_route():

    router = SmartRouter()

    executor = lambda: "ok"

    router.register(
        "primary",
        executor,
    )

    assert router.has_route(
        "primary",
    )


def test_registered_route_is_available():

    router = SmartRouter()

    router.register(
        "primary",
        lambda: "ok",
    )

    assert router.available_routes() == [
        "primary",
    ]


def test_unregister_route():

    router = SmartRouter()

    router.register(
        "primary",
        lambda: "ok",
    )

    router.unregister(
        "primary",
    )

    assert not router.has_route(
        "primary",
    )


def test_unregister_missing_route_is_safe():

    router = SmartRouter()

    router.unregister(
        "missing",
    )

    assert router.available_routes() == []


def test_preferred_route_is_selected():

    router = SmartRouter()

    decision = router.route(
        [
            RouteCandidate(
                name="primary",
                priority=10,
            ),
            RouteCandidate(
                name="secondary",
                priority=100,
            ),
        ],
        preferred_route="primary",
    )

    assert decision.route == "primary"


def test_highest_priority_route_is_selected():

    router = SmartRouter()

    decision = router.route(
        [
            RouteCandidate(
                name="primary",
                priority=10,
            ),
            RouteCandidate(
                name="secondary",
                priority=100,
            ),
        ],
    )

    assert decision.route == "secondary"


def test_unavailable_route_is_ignored():

    router = SmartRouter()

    decision = router.route(
        [
            RouteCandidate(
                name="primary",
                available=False,
                priority=100,
            ),
            RouteCandidate(
                name="secondary",
                available=True,
                priority=10,
            ),
        ],
    )

    assert decision.route == "secondary"


def test_preferred_unavailable_route_falls_back():

    router = SmartRouter()

    decision = router.route(
        [
            RouteCandidate(
                name="primary",
                available=False,
                priority=100,
            ),
            RouteCandidate(
                name="secondary",
                available=True,
                priority=10,
            ),
        ],
        preferred_route="primary",
    )

    assert decision.route == "secondary"


def test_no_candidates_is_rejected():

    router = SmartRouter()

    with pytest.raises(
        ValueError,
        match="At least one route candidate",
    ):

        router.route(
            [],
        )


def test_no_available_routes_is_rejected():

    router = SmartRouter()

    with pytest.raises(
        RuntimeError,
        match="No available execution route",
    ):

        router.route(
            [
                RouteCandidate(
                    name="primary",
                    available=False,
                ),
            ],
        )


def test_routing_decision_type():

    router = SmartRouter()

    decision = router.route(
        [
            RouteCandidate(
                name="primary",
            ),
        ],
    )

    assert isinstance(
        decision,
        RoutingDecision,
    )


def test_execute_calls_selected_executor():

    router = SmartRouter()

    def executor(
        value,
    ):

        return value * 2

    router.register(
        "primary",
        executor,
    )

    result = router.execute(
        [
            RouteCandidate(
                name="primary",
            ),
        ],
        args=(5,),
    )

    assert result == 10


def test_execute_passes_keyword_arguments():

    router = SmartRouter()

    def executor(
        *,
        value,
    ):

        return value + 1

    router.register(
        "primary",
        executor,
    )

    result = router.execute(
        [
            RouteCandidate(
                name="primary",
            ),
        ],
        kwargs={
            "value": 4,
        },
    )

    assert result == 5


def test_execute_unregistered_route_is_rejected():

    router = SmartRouter()

    with pytest.raises(
        RuntimeError,
        match="not registered",
    ):

        router.execute(
            [
                RouteCandidate(
                    name="primary",
                ),
            ],
        )


def test_register_rejects_invalid_name():

    router = SmartRouter()

    with pytest.raises(
        ValueError,
        match="route name cannot be empty",
    ):

        router.register(
            "",
            lambda: None,
        )


def test_register_rejects_non_callable_executor():

    router = SmartRouter()

    with pytest.raises(
        TypeError,
        match="executor must be callable",
    ):

        router.register(
            "primary",
            "not callable",
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
def test_has_route_rejects_empty_name(
    name,
):

    router = SmartRouter()

    with pytest.raises(
        ValueError,
        match="route name cannot be empty",
    ):

        router.has_route(
            name,
        )


@pytest.mark.parametrize(
    "name",
    [
        None,
        123,
        [],
        {},
        True,
    ],
)
def test_register_rejects_invalid_name_type(
    name,
):

    router = SmartRouter()

    with pytest.raises(
        TypeError,
        match="route name must be a string",
    ):

        router.register(
            name,
            lambda: None,
        )


def test_preferred_route_reason_is_correct():

    router = SmartRouter()

    decision = router.route(
        [
            RouteCandidate(
                name="primary",
            ),
        ],
        preferred_route="primary",
    )

    assert (
        decision.reason
        == "Preferred route selected."
    )


def test_priority_route_reason_is_correct():

    router = SmartRouter()

    decision = router.route(
        [
            RouteCandidate(
                name="primary",
            ),
        ],
    )

    assert (
        decision.reason
        == "Highest-priority available "
        "route selected."
    )