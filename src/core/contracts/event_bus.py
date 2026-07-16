from abc import ABC, abstractmethod

from src.core.event_bus.event import Event


class IEventBus(ABC):

    @abstractmethod
    def publish(self, event: Event) -> None:
        ...

    @abstractmethod
    def subscribe(self, event_name: str, handler) -> None:
        ...

    @abstractmethod
    def unsubscribe(self, event_name: str, handler) -> None:
        ...