"""Immutable canonical payloads for deterministic in-memory replay."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.data.adapters.errors import InvalidRecordedPayloadError

_SENSITIVE_KEY = re.compile(
    r"(?i)(api[_-]?key|api[_-]?secret|authorization|credential|"
    r"password|passphrase|private[_-]?key|secret|token)"
)


class RecordedPayloadKind(str, Enum):
    """Supported local ingestion operations."""

    SNAPSHOT = "snapshot"
    CANDLES = "candles"
    ORDER_BOOK = "order_book"


def _validate_json_value(value: object) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if (
                not isinstance(key, str)
                or _SENSITIVE_KEY.search(key)
            ):
                raise InvalidRecordedPayloadError
            _validate_json_value(item)
        return
    raise InvalidRecordedPayloadError


def _canonical_payload(payload: object) -> str:
    if not isinstance(payload, dict):
        raise InvalidRecordedPayloadError
    _validate_json_value(payload)
    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError, OverflowError) as error:
        raise InvalidRecordedPayloadError from error


@dataclass(frozen=True, slots=True)
class RecordedMarketDataPayload:
    """One immutable canonical JSON event with deterministic integrity hash."""

    sequence: int
    kind: RecordedPayloadKind
    payload_json: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise InvalidRecordedPayloadError
        if not isinstance(self.kind, RecordedPayloadKind):
            raise InvalidRecordedPayloadError
        if not isinstance(self.payload_json, str) or not self.payload_json:
            raise InvalidRecordedPayloadError
        try:
            parsed = json.loads(self.payload_json)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise InvalidRecordedPayloadError from error
        canonical = _canonical_payload(parsed)
        if canonical != self.payload_json:
            raise InvalidRecordedPayloadError

    @classmethod
    def from_mapping(
        cls,
        *,
        sequence: int,
        kind: RecordedPayloadKind,
        payload: Mapping[str, Any],
    ) -> RecordedMarketDataPayload:
        """Defensively canonicalize a caller-owned JSON mapping."""

        if not isinstance(payload, Mapping):
            raise InvalidRecordedPayloadError
        materialized = dict(payload)
        return cls(
            sequence=sequence,
            kind=kind,
            payload_json=_canonical_payload(materialized),
        )

    @property
    def digest(self) -> str:
        """Return a deterministic SHA-256 integrity digest."""

        material = (
            f"{self.sequence}:{self.kind.value}:{self.payload_json}"
        ).encode("utf-8")
        return hashlib.sha256(material).hexdigest()

    def to_mapping(self) -> dict[str, Any]:
        """Return a fresh mutable decoding of the immutable payload."""

        parsed = json.loads(self.payload_json)
        if not isinstance(parsed, dict):
            raise InvalidRecordedPayloadError
        return parsed


@dataclass(frozen=True, slots=True)
class ReplayResult:
    """Deterministic summary of one successful replay call."""

    applied: int
    last_sequence: int | None
    digests: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            isinstance(self.applied, bool)
            or not isinstance(self.applied, int)
            or self.applied < 0
            or self.applied != len(self.digests)
        ):
            raise ValueError("Replay result is inconsistent.")
        if self.last_sequence is not None and (
            isinstance(self.last_sequence, bool)
            or not isinstance(self.last_sequence, int)
            or self.last_sequence < 0
        ):
            raise ValueError("Replay result sequence is invalid.")


__all__ = (
    "RecordedMarketDataPayload",
    "RecordedPayloadKind",
    "ReplayResult",
)
