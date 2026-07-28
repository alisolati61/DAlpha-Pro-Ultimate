"""Immutable contracts for deterministic strategy proposals."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from math import isfinite


class ProposalDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"


def _price(value: float | None, name: str) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return round(number, 8)


@dataclass(frozen=True, slots=True)
class TradeProposal:
    proposal_id: str
    symbol: str
    exchange: str
    timeframe: str
    direction: ProposalDirection
    entry_reference_price: float
    stop_loss_candidate: float | None
    take_profit_candidate: float | None
    confidence: float
    strategy_id: str
    strategy_version: str
    timestamp: datetime
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        text_fields = (
            "proposal_id", "symbol", "exchange", "timeframe",
            "strategy_id", "strategy_version",
        )
        for name in text_fields:
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be empty")
            object.__setattr__(self, name, value.strip())
        if not isinstance(self.direction, ProposalDirection):
            raise TypeError("direction must be a ProposalDirection")
        entry = _price(self.entry_reference_price, "entry_reference_price")
        stop = _price(self.stop_loss_candidate, "stop_loss_candidate")
        target = _price(self.take_profit_candidate, "take_profit_candidate")
        confidence = round(float(self.confidence), 8)
        if not isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("confidence must be between zero and one")
        timestamp = self.timestamp
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        reasons = tuple(sorted(set(self.reason_codes)))
        if not reasons or any(not item or item != item.strip() for item in reasons):
            raise ValueError("reason_codes must contain non-empty values")
        if self.direction is ProposalDirection.HOLD:
            if stop is not None or target is not None:
                raise ValueError("HOLD cannot contain trade price candidates")
        object.__setattr__(self, "entry_reference_price", entry)
        object.__setattr__(self, "stop_loss_candidate", stop)
        object.__setattr__(self, "take_profit_candidate", target)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "timestamp", timestamp.astimezone(UTC))
        object.__setattr__(self, "reason_codes", reasons)

    def to_dict(self) -> dict[str, object]:
        return {
            "proposal_id": self.proposal_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "timeframe": self.timeframe,
            "direction": self.direction.value,
            "entry_reference_price": self.entry_reference_price,
            "stop_loss_candidate": self.stop_loss_candidate,
            "take_profit_candidate": self.take_profit_candidate,
            "confidence": self.confidence,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"),
            "reason_codes": list(self.reason_codes),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        )

    @staticmethod
    def deterministic_id(values: Mapping[str, object]) -> str:
        payload = json.dumps(
            values, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = ("ProposalDirection", "TradeProposal")
