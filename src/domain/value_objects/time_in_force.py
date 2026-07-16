from __future__ import annotations

from enum import Enum


class TimeInForce(str, Enum):
    """
    Order time-in-force policy.
    """

    GTC = "GTC"  # Good Till Cancelled
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill
    GTX = "GTX"  # Post Only

    @property
    def is_post_only(self) -> bool:
        return self is TimeInForce.GTX

    @property
    def requires_immediate_execution(self) -> bool:
        return self in {
            TimeInForce.IOC,
            TimeInForce.FOK,
        }