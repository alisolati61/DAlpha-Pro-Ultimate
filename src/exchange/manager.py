from __future__ import annotations

from typing import Dict

from src.exchange.ccxt_exchange import CCXTExchange


class ExchangeManager:
    """
    Central manager for exchange instances.

    Features
    --------
    - Singleton exchange objects
    - Lazy initialization
    - Connection lifecycle
    """

    def __init__(self) -> None:

        self._instances: Dict[str, CCXTExchange] = {}

    # ------------------------------------------------

    def register(
        self,
        name: str,
        exchange: CCXTExchange,
    ) -> None:

        self._instances[name] = exchange

    # ------------------------------------------------

    def get(
        self,
        name: str,
    ) -> CCXTExchange:

        return self._instances[name]

    # ------------------------------------------------

    def exists(
        self,
        name: str,
    ) -> bool:

        return name in self._instances

    # ------------------------------------------------

    def remove(
        self,
        name: str,
    ) -> None:

        self._instances.pop(name, None)

    # ------------------------------------------------

    def names(self) -> list[str]:

        return list(self._instances.keys())

    # ------------------------------------------------

    async def shutdown(self) -> None:

        for exchange in self._instances.values():

            await exchange.disconnect()

        self._instances.clear()