"""Behavioral tests for exchange exception metadata and safety."""

from __future__ import annotations

from copy import deepcopy

import pytest

from src.core.exceptions.base import AlphaError
from src.exchange.exceptions import (
    AuthenticationError,
    ExchangeError,
    ExchangeNotAvailableError,
    InsufficientFundsError,
    InvalidSymbolError,
    NetworkError,
    OrderError,
    RateLimitError,
    WebSocketError,
)


def test_exchange_error_preserves_normalized_metadata() -> None:
    error = ExchangeError(
        message="  request failed  ",
        exchange="  BiNgX  ",
        error_code=100500,
        operation="  fetch_balance  ",
    )

    assert isinstance(error, AlphaError)
    assert isinstance(error, Exception)
    assert str(error) == "request failed"
    assert error.message == "request failed"
    assert error.exchange == "bingx"
    assert error.error_code == "100500"
    assert error.operation == "fetch_balance"
    assert error.retryable is False
    assert error.raw_response == {}


def test_raw_response_is_copied_and_sensitive_values_are_redacted() -> None:
    response = {
        "code": 100401,
        "apiKey": "public-secret",
        "nested": {
            "secret_key": "private-secret",
            "Authorization": "Bearer token",
            "safe": "visible",
        },
        "items": [
            {
                "refresh_token": "refresh-secret",
                "value": 42,
            }
        ],
    }
    original = deepcopy(response)

    error = AuthenticationError(
        "credentials rejected",
        exchange="bingx",
        raw_response=response,
    )

    assert response == original
    assert error.raw_response == {
        "code": 100401,
        "apiKey": "<redacted>",
        "nested": {
            "secret_key": "<redacted>",
            "Authorization": "<redacted>",
            "safe": "visible",
        },
        "items": [
            {
                "refresh_token": "<redacted>",
                "value": 42,
            }
        ],
    }

    response["nested"]["safe"] = "changed"

    assert error.raw_response["nested"]["safe"] == "visible"


def test_recursive_raw_response_is_handled_safely() -> None:
    response: dict[str, object] = {"code": 1}
    response["self"] = response

    error = ExchangeError(
        "recursive response",
        raw_response=response,
    )

    assert error.raw_response == {
        "code": 1,
        "self": "<recursive>",
    }


def test_string_and_repr_do_not_include_raw_response() -> None:
    error = ExchangeError(
        "request failed",
        exchange="bingx",
        raw_response={"password": "super-secret"},
    )

    assert "super-secret" not in str(error)
    assert "super-secret" not in repr(error)
    assert "raw_response" not in repr(error)


def test_to_dict_excludes_raw_response_by_default() -> None:
    error = ExchangeError(
        "request failed",
        exchange="bingx",
        error_code="E-1",
        raw_response={"signature": "secret"},
        operation="create_order",
    )

    assert error.to_dict() == {
        "type": "ExchangeError",
        "message": "request failed",
        "exchange": "bingx",
        "error_code": "E-1",
        "operation": "create_order",
        "retryable": False,
    }

    assert error.to_dict(
        include_raw_response=True
    )["raw_response"] == {
        "signature": "<redacted>"
    }


@pytest.mark.parametrize(
    ("error_type", "retryable"),
    [
        (ExchangeError, False),
        (AuthenticationError, False),
        (InsufficientFundsError, False),
        (InvalidSymbolError, False),
        (OrderError, False),
        (RateLimitError, True),
        (NetworkError, True),
        (WebSocketError, True),
        (ExchangeNotAvailableError, True),
    ],
)
def test_retryability_defaults(
    error_type: type[ExchangeError],
    retryable: bool,
) -> None:
    error = error_type("failure", exchange="bingx")

    assert error.retryable is retryable


def test_retryability_can_be_overridden_explicitly() -> None:
    network_error = NetworkError(
        "permanent network rejection",
        retryable=False,
    )
    order_error = OrderError(
        "temporary order rejection",
        retryable=True,
    )

    assert network_error.retryable is False
    assert order_error.retryable is True


def test_network_exception_hierarchy_supports_retry_classification() -> None:
    assert issubclass(WebSocketError, NetworkError)
    assert issubclass(
        ExchangeNotAvailableError,
        NetworkError,
    )


def test_rate_limit_error_accepts_numeric_retry_after_string() -> None:
    error = RateLimitError(
        "slow down",
        exchange="bingx",
        retry_after="2.5",
        error_code=100429,
    )

    assert error.retry_after == 2.5
    assert error.to_dict()["retry_after"] == 2.5
    assert error.retryable is True


@pytest.mark.parametrize("retry_after", [-1, float("inf"), float("nan")])
def test_invalid_retry_after_value_is_rejected(
    retry_after: float,
) -> None:
    with pytest.raises(ValueError):
        RateLimitError(
            "slow down",
            retry_after=retry_after,
        )


@pytest.mark.parametrize(
    "retry_after",
    [True, object(), "not-a-number"],
)
def test_invalid_retry_after_type_is_rejected(
    retry_after: object,
) -> None:
    with pytest.raises(TypeError):
        RateLimitError(
            "slow down",
            retry_after=retry_after,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("kwargs", "error_type", "message"),
    [
        (
            {"message": 123},
            TypeError,
            "message must be a string",
        ),
        (
            {"message": "   "},
            ValueError,
            "message cannot be empty",
        ),
        (
            {
                "message": "failure",
                "exchange": "",
            },
            ValueError,
            "exchange cannot be empty",
        ),
        (
            {
                "message": "failure",
                "raw_response": [],
            },
            TypeError,
            "raw_response must be a mapping",
        ),
        (
            {
                "message": "failure",
                "retryable": "yes",
            },
            TypeError,
            "retryable must be a boolean",
        ),
    ],
)
def test_invalid_exchange_error_metadata_is_rejected(
    kwargs: dict[str, object],
    error_type: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        ExchangeError(**kwargs)  # type: ignore[arg-type]