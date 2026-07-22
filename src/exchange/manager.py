from __future__ import annotations

from typing import Any


class ExchangeManager:
    """
    Central manager for registered exchanges.

    Supports lazy registration by name and registration
    of already-created exchange instances.
    """

    def __init__(self) -> None:
        self._instances: dict[str, Any] = {}

    def register(
        self,
        name: str,
        exchange: Any | None = None,
    ) -> None:
        if not isinstance(name, str):
            raise TypeError(
                "Exchange name must be a string."
            )

        normalized_name = name.strip()

        if not normalized_name:
            raise ValueError(
                "Exchange name cannot be empty."
            )

        self._instances[
            normalized_name
        ] = exchange

    def get(self, name: str) -> Any:
        return self._instances[name]

    def exists(self, name: str) -> bool:
        return name in self._instances

    def remove(self, name: str) -> None:
        self._instances.pop(name, None)

    def list(self) -> list[str]:
        return list(self._instances.keys())

    def names(self) -> list[str]:
        return self.list()

    async def shutdown(self) -> None:
        for exchange in self._instances.values():
            if exchange is None:
                continue

            disconnect = getattr(
                exchange,
                "disconnect",
                None,
            )

            if disconnect is None:
                continue

            result = disconnect()

            if hasattr(result, "__await__"):
                await result

        self._instances.clear()