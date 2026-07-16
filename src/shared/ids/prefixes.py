from enum import Enum


class IdPrefix(str, Enum):
    ORDER = "ORD"
    TRADE = "TRD"
    POSITION = "POS"
    STRATEGY = "STR"
    EVENT = "EVT"
    SESSION = "SES"