from abc import ABC, abstractmethod


class BaseDriver(ABC):
    """
    Base class for all exchange drivers.
    """

    @abstractmethod
    def connect(self) -> None:
        """Open connection."""
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection."""
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        """Return driver health status."""
        raise NotImplementedError