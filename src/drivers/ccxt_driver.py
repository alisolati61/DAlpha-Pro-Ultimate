from typing import Any, Optional

import ccxt

from .base_driver import BaseDriver


class CCXTDriver(BaseDriver):
    """
    Generic CCXT driver for supported exchanges.
    """

    def __init__(
        self,
        exchange_name: str,
        config: Optional[dict[str, Any]] = None,
    ):
        self.exchange_name = exchange_name
        self.config = config or {}
        self.exchange: Optional[ccxt.Exchange] = None

    def connect(self) -> None:
        exchange_class = getattr(ccxt, self.exchange_name)
        self.exchange = exchange_class(self.config)

    def disconnect(self) -> None:
        self.exchange = None

    def health_check(self) -> bool:
        return self.exchange is not None