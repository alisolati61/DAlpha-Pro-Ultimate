from typing import Dict

from .base import BaseExchange
from .ccxt_exchange import CCXTExchange


class ExchangeManager:

    def __init__(self):
        self._connectors: Dict[str, BaseExchange] = {}

    def register(self, name: str):

        if name not in self._connectors:
            self._connectors[name] = CCXTExchange(name)

    def get(self, name: str) -> BaseExchange | None:
        return self._connectors.get(name)

    def remove(self, name: str):

        if name in self._connectors:
            del self._connectors[name]

    def exists(self, name: str) -> bool:
        return name in self._connectors

    def list(self):
        return list(self._connectors.keys())

    def count(self):
        return len(self._connectors)

    def clear(self):
        self._connectors.clear()