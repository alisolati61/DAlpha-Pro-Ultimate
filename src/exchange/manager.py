"""Registry and lifecycle coordination for exchange adapters."""

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Self

from src.exchange.base import BaseExchange


class ExchangeManager:
    """Own named exchange adapters and coordinate deterministic shutdown."""

    def __init__(self) -> None:
        self._instances: dict[str, BaseExchange] = {}
        self._shutdown_lock = asyncio.Lock()
        self._shutting_down = False

    def register(
        self,
        name: str,
        exchange: BaseExchange,
    ) -> None:
        """Register one adapter under a normalized, unique name."""

        self._ensure_mutable()
        normalized_name = self._normalize_name(name)

        if not isinstance(exchange, BaseExchange):
            raise TypeError(
                "Exchange must implement the BaseExchange contract."
            )

        if normalized_name in self._instances:
            raise ValueError(
                f"Exchange is already registered: {normalized_name}"
            )

        self._instances[normalized_name] = exchange

    def get(self, name: str) -> BaseExchange:
        """Return a registered adapter or raise a descriptive error."""

        normalized_name = self._normalize_name(name)

        try:
            return self._instances[normalized_name]
        except KeyError as exc:
            raise KeyError(
                f"Exchange is not registered: {normalized_name}"
            ) from exc

    def exists(self, name: str) -> bool:
        """Return whether a normalized exchange name is registered."""

        normalized_name = self._normalize_name(name)
        return normalized_name in self._instances

    def remove(self, name: str) -> BaseExchange:
        """Remove and return an adapter without disconnecting it."""

        self._ensure_mutable()
        normalized_name = self._normalize_name(name)

        try:
            return self._instances.pop(normalized_name)
        except KeyError as exc:
            raise KeyError(
                f"Exchange is not registered: {normalized_name}"
            ) from exc

    def names(self) -> list[str]:
        """Return registered names in insertion order."""

        return list(self._instances)

    def list(self) -> list[str]:
        """Backward-compatible alias for :meth:`names`."""

        return self.names()

    def __len__(self) -> int:
        return len(self._instances)

    def __contains__(self, name: object) -> bool:
        if not isinstance(name, str):
            return False

        try:
            return self.exists(name)
        except ValueError:
            return False

    async def shutdown(self) -> None:
        """Disconnect every owned adapter without hiding partial failures.

        All registered adapters receive a disconnect attempt. Successfully
        disconnected adapters are removed. Failed or cancelled adapters remain
        registered so shutdown can be retried safely.
        """

        async with self._shutdown_lock:
            if not self._instances:
                return

            self._shutting_down = True
            registered = tuple(self._instances.items())

            try:
                results = await asyncio.gather(
                    *(exchange.disconnect() for _, exchange in registered),
                    return_exceptions=True,
                )

                failures: list[Exception] = []

                for (name, exchange), result in zip(
                    registered,
                    results,
                    strict=True,
                ):
                    if isinstance(result, BaseException):
                        failure = RuntimeError(
                            f"Failed to disconnect exchange '{name}': "
                            f"{result}"
                        )
                        failure.__cause__ = result
                        failures.append(failure)
                        continue

                    if self._instances.get(name) is exchange:
                        del self._instances[name]

                if failures:
                    raise ExceptionGroup(
                        "One or more exchanges failed to disconnect.",
                        failures,
                    )
            finally:
                self._shutting_down = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        await self.shutdown()
        return False

    def _ensure_mutable(self) -> None:
        if self._shutting_down:
            raise RuntimeError(
                "Cannot modify the exchange registry while shutdown "
                "is in progress."
            )

    @staticmethod
    def _normalize_name(name: str) -> str:
        if not isinstance(name, str):
            raise TypeError("Exchange name must be a string.")

        normalized_name = name.strip().casefold()

        if not normalized_name:
            raise ValueError("Exchange name cannot be empty.")

        return normalized_name


__all__ = ("ExchangeManager",)