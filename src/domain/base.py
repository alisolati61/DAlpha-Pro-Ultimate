from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class BaseModel:
    """
    Base class for all DALPHA domain models.
    """

    exchange: Optional[str] = None
    timestamp: Optional[datetime] = None