"""Typed and security-conscious exceptions for exchange operations."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, ClassVar

from src.core.exceptions.base import AlphaError

_REDACTED = "<redacted>"
_RECURSIVE = "<recursive>"
_SENSITIVE_KEY_TOKENS = frozenset(
    {
        "apikey",
        "apisecret",
        "authorization",
        "password",
        "passphrase",
        "refreshtoken",
        "secret",
        "secretkey",
        "signature",
        "token",
    }
)


def _normalized_key(value: object) -> str:
    return "".join(
        character
        for character in str(value).casefold()
        if character.isalnum()
    )


def _is_sensitive_key(value: object) -> bool:
    normalized = _normalized_key(value)
    return any(
        normalized == token or normalized.endswith(token)
        for token in _SENSITIVE_KEY_TOKENS
    )


def _sanitize_value(
    value: Any,
    *,
    key: object | None = None,
    seen: set[int] | None = None,
) -> Any:
    if key is not None and _is_sensitive_key(key):
        return _REDACTED

    if seen is None:
        seen = set()

    if isinstance(value, Mapping):
        object_id = id(value)

        if object_id in seen:
            return _RECURSIVE

        seen.add(object_id)

        try:
            return {
                str(item_key): _sanitize_value(
                    item_value,
                    key=item_key,
                    seen=seen,
                )
                for item_key, item_value in value.items()
            }
        finally:
            seen.remove(object_id)

    if isinstance(value, list):
        object_id = id(value)

        if object_id in seen:
            return _RECURSIVE

        seen.add(object_id)

        try:
            return [
                _sanitize_value(item, seen=seen)
                for item in value
            ]
        finally:
            seen.remove(object_id)

    if isinstance(value, tuple):
        object_id = id(value)

        if object_id in seen:
            return _RECURSIVE

        seen.add(object_id)

        try:
            return tuple(
                _sanitize_value(item, seen=seen)
                for item in value
            )
        finally:
            seen.remove(object_id)

    return value


class ExchangeError(AlphaError):
    """Base exception for failures at the exchange boundary."""

    default_retryable: ClassVar[bool] = False

    def __init__(
        self,
        message: str,
        exchange: str = "unknown",
        error_code: str | int | None = None,
        raw_response: Mapping[str, Any] | None = None,
        *,
        operation: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        normalized_message = self._normalize_required_text(
            message,
            field_name="message",
        )
        normalized_exchange = self._normalize_exchange(exchange)

        if operation is not None:
            operation = self._normalize_required_text(
                operation,
                field_name="operation",
            )

        if retryable is not None and not isinstance(retryable, bool):
            raise TypeError("retryable must be a boolean or None.")

        if raw_response is not None and not isinstance(
            raw_response,
            Mapping,
        ):
            raise TypeError(
                "raw_response must be a mapping or None."
            )

        super().__init__(normalized_message)

        self.message = normalized_message
        self.exchange = normalized_exchange
        self.error_code = (
            None if error_code is None else str(error_code)
        )
        self.operation = operation
        self.retryable = (
            self.default_retryable
            if retryable is None
            else retryable
        )
        self.raw_response: dict[str, Any] = (
            {}
            if raw_response is None
            else _sanitize_value(raw_response)
        )

    def to_dict(
        self,
        *,
        include_raw_response: bool = False,
    ) -> dict[str, Any]:
        """Return structured, log-safe exception metadata."""

        payload: dict[str, Any] = {
            "type": type(self).__name__,
            "message": self.message,
            "exchange": self.exchange,
            "error_code": self.error_code,
            "operation": self.operation,
            "retryable": self.retryable,
        }

        if include_raw_response:
            payload["raw_response"] = _sanitize_value(
                self.raw_response
            )

        return payload

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"message={self.message!r}, "
            f"exchange={self.exchange!r}, "
            f"error_code={self.error_code!r}, "
            f"operation={self.operation!r}, "
            f"retryable={self.retryable!r})"
        )

    @staticmethod
    def _normalize_required_text(
        value: str,
        *,
        field_name: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{field_name} must be a string.")

        normalized = value.strip()

        if not normalized:
            raise ValueError(f"{field_name} cannot be empty.")

        return normalized

    @classmethod
    def _normalize_exchange(cls, exchange: str) -> str:
        return cls._normalize_required_text(
            exchange,
            field_name="exchange",
        ).casefold()


class AuthenticationError(ExchangeError):
    """Credentials are invalid, expired, or lack permission."""


class RateLimitError(ExchangeError):
    """The exchange rejected a request because of rate limiting."""

    default_retryable = True

    def __init__(
        self,
        message: str,
        exchange: str = "unknown",
        retry_after: int | float | str | None = 60,
        *,
        error_code: str | int | None = None,
        raw_response: Mapping[str, Any] | None = None,
        operation: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(
            message=message,
            exchange=exchange,
            error_code=error_code,
            raw_response=raw_response,
            operation=operation,
            retryable=retryable,
        )
        self.retry_after = self._normalize_retry_after(
            retry_after
        )

    def to_dict(
        self,
        *,
        include_raw_response: bool = False,
    ) -> dict[str, Any]:
        payload = super().to_dict(
            include_raw_response=include_raw_response
        )
        payload["retry_after"] = self.retry_after
        return payload

    @staticmethod
    def _normalize_retry_after(
        value: int | float | str | None,
    ) -> float | None:
        if value is None:
            return None

        if isinstance(value, bool):
            raise TypeError(
                "retry_after must be numeric, a numeric string, "
                "or None."
            )

        try:
            normalized = float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                "retry_after must be numeric, a numeric string, "
                "or None."
            ) from exc

        if not math.isfinite(normalized):
            raise ValueError("retry_after must be finite.")

        if normalized < 0:
            raise ValueError(
                "retry_after cannot be negative."
            )

        return normalized


class InsufficientFundsError(ExchangeError):
    """The account lacks sufficient available balance."""


class InvalidSymbolError(ExchangeError):
    """The requested market symbol is invalid or unsupported."""


class OrderError(ExchangeError):
    """An order operation failed or was rejected."""


class NetworkError(ExchangeError):
    """A transport, connection, or timeout operation failed."""

    default_retryable = True


class WebSocketError(NetworkError):
    """A WebSocket connection or message operation failed."""


class ExchangeNotAvailableError(NetworkError):
    """The exchange is unavailable or under maintenance."""


__all__ = (
    "AuthenticationError",
    "ExchangeError",
    "ExchangeNotAvailableError",
    "InsufficientFundsError",
    "InvalidSymbolError",
    "NetworkError",
    "OrderError",
    "RateLimitError",
    "WebSocketError",
)