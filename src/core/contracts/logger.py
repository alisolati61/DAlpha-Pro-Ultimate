from abc import ABC, abstractmethod


class ILogger(ABC):

    @abstractmethod
    def debug(self, message: str) -> None:
        ...

    @abstractmethod
    def info(self, message: str) -> None:
        ...

    @abstractmethod
    def warning(self, message: str) -> None:
        ...

    @abstractmethod
    def error(self, message: str) -> None:
        ...

    @abstractmethod
    def critical(self, message: str) -> None:
        ...