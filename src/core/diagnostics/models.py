"""Immutable public contracts for safe runtime diagnostics."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from numbers import Real
from typing import Any

_SENSITIVE_TEXT = re.compile(
    r"(?i)(api[_-]?key|api[_-]?secret|authorization|bearer|"
    r"password|passphrase|private[_-]?key|refresh[_-]?token|"
    r"secret[_-]?key|traceback)"
)
_ABSOLUTE_PATH = re.compile(
    r"(?i)(?:[a-z]:[\\/]|/(?:home|root|users|var|etc|tmp)/)"
)
_WITHHELD_MESSAGE = "Diagnostic details withheld."


class DiagnosticStatus(str, Enum):
    """Stable status values exposed by diagnostic reports."""

    PASS = "pass"
    FAIL = "fail"


def sanitize_public_message(message: object) -> str:
    """Return a single-line message without sensitive diagnostic details."""

    if not isinstance(message, str):
        return _WITHHELD_MESSAGE

    normalized = " ".join(message.split())

    if (
        not normalized
        or _SENSITIVE_TEXT.search(normalized)
        or _ABSOLUTE_PATH.search(normalized)
    ):
        return _WITHHELD_MESSAGE

    return normalized


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{field_name} cannot be empty.")

    return normalized


def _duration(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be numeric.")

    normalized = float(value)

    if not math.isfinite(normalized) or normalized < 0:
        raise ValueError(
            f"{field_name} must be finite and non-negative."
        )

    return normalized


def _utc_timestamp(value: object, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")

    return value.astimezone(UTC)


def _timestamp_text(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace(
        "+00:00",
        "Z",
    )


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    """One immutable, safely publishable diagnostic result."""

    name: str
    status: DiagnosticStatus
    message: str
    duration_ms: float

    def __post_init__(self) -> None:
        if not isinstance(self.status, DiagnosticStatus):
            raise TypeError("status must be a DiagnosticStatus.")

        object.__setattr__(
            self,
            "name",
            sanitize_public_message(
                _required_text(self.name, "name")
            ),
        )
        object.__setattr__(
            self,
            "message",
            sanitize_public_message(self.message),
        )
        object.__setattr__(
            self,
            "duration_ms",
            _duration(self.duration_ms, "duration_ms"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic primitive mapping."""

        return {
            "duration_ms": self.duration_ms,
            "message": self.message,
            "name": self.name,
            "status": self.status.value,
        }


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    """Immutable aggregate report produced by the Doctor."""

    application: str
    version: str
    mode: str
    success: bool
    started_at: datetime
    finished_at: datetime
    duration_ms: float
    checks: tuple[DiagnosticCheck, ...]

    def __post_init__(self) -> None:
        application = sanitize_public_message(
            _required_text(self.application, "application")
        )
        version = sanitize_public_message(
            _required_text(self.version, "version")
        )
        mode = sanitize_public_message(
            _required_text(self.mode, "mode")
        )

        if type(self.success) is not bool:
            raise TypeError("success must be a bool.")

        started_at = _utc_timestamp(self.started_at, "started_at")
        finished_at = _utc_timestamp(self.finished_at, "finished_at")

        if finished_at < started_at:
            raise ValueError(
                "finished_at cannot be earlier than started_at."
            )

        if not isinstance(self.checks, tuple) or not all(
            isinstance(check, DiagnosticCheck)
            for check in self.checks
        ):
            raise TypeError(
                "checks must be a tuple of DiagnosticCheck objects."
            )

        expected_success = all(
            check.status is DiagnosticStatus.PASS
            for check in self.checks
        )

        if self.success is not expected_success:
            raise ValueError(
                "success must match the aggregate check status."
            )

        object.__setattr__(self, "application", application)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "started_at", started_at)
        object.__setattr__(self, "finished_at", finished_at)
        object.__setattr__(
            self,
            "duration_ms",
            _duration(self.duration_ms, "duration_ms"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-compatible mapping."""

        return {
            "application": self.application,
            "checks": [
                check.to_dict()
                for check in self.checks
            ],
            "duration_ms": self.duration_ms,
            "finished_at": _timestamp_text(self.finished_at),
            "mode": self.mode,
            "started_at": _timestamp_text(self.started_at),
            "success": self.success,
            "version": self.version,
        }

    def to_json(self) -> str:
        """Serialize deterministically without environment-specific details."""

        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )


__all__ = (
    "DiagnosticCheck",
    "DiagnosticReport",
    "DiagnosticStatus",
    "sanitize_public_message",
)
