from dataclasses import dataclass
from typing import Optional

from .base import BaseModel


@dataclass(slots=True)
class Order(BaseModel):
    """
    Standard order model used across the entire DALPHA system.
    """

    symbol: str = ""
    side: str = ""
    order_type: str = ""
    quantity: float = 0.0
    price: Optional[float] = None