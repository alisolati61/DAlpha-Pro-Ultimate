from __future__ import annotations

from abc import ABC, abstractmethod

from src.analysis.signal_engine import Signal


class BaseStrategy(ABC):
    """
    Base class for every trading strategy.
    """

    @abstractmethod
    def generate_signal(self) -> Signal:
        pass


class StrategyEngine:

    def __init__(self):

        self._strategies: list[BaseStrategy] = []

    def register(
        self,
        strategy: BaseStrategy,
    ) -> None:

        self._strategies.append(strategy)

    def strategies(self):

        return self._strategies

    def run(self) -> list[Signal]:

        return [
            strategy.generate_signal()
            for strategy in self._strategies
        ]