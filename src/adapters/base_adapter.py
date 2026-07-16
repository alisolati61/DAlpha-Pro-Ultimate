from abc import ABC
from src.interfaces.exchange_interface import ExchangeInterface
from src.drivers.base_driver import BaseDriver


class BaseAdapter(ExchangeInterface, ABC):
    """
    Base adapter for all exchange adapters.
    """

    def __init__(self, driver: BaseDriver):
        self.driver = driver