from __future__ import annotations

from abc import ABC, abstractmethod

from src.analysis.signal_engine import Signal
from src.domain.candle_series import CandleSeries


class ICTModule(ABC):
    """
    Base class for every ICT component.
    """

    @abstractmethod
    def analyze(
        self,
        series: CandleSeries,
    ) -> Signal:
        pass


class ICTEngine:

    def __init__(self):

        self._modules: list[ICTModule] = []

    def register(
        self,
        module: ICTModule,
    ) -> None:

        self._modules.append(module)

    def modules(self):

        return self._modules

    def analyze(
        self,
        series: CandleSeries,
    ) -> list[Signal]:

        return [
            module.analyze(series)
            for module in self._modules
        ]