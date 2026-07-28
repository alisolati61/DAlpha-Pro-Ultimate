"""Immutable contracts for the local Doctor runtime configuration."""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.core.kernel.runtime import RuntimeMode

KNOWN_ENVIRONMENTS = frozenset(
    {"development", "test", "staging", "production"}
)
KNOWN_LOG_LEVELS = frozenset(
    {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
)

_SENSITIVE_TEXT = re.compile(
    r"(?i)(api[_-]?key|api[_-]?secret|authorization|bearer|"
    r"credential|password|passphrase|private[_-]?key|secret|token)"
)
_WITHHELD_VALUE = "<withheld>"
_ABSOLUTE_PATH = "<absolute-path>"


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")

    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty.")
    return normalized


def _path_value(value: object, field_name: str) -> Path:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be path-compatible.")

    try:
        raw_path = os.fspath(value)  # type: ignore[call-overload]
    except TypeError as error:
        raise TypeError(
            f"{field_name} must be path-compatible."
        ) from error

    if isinstance(raw_path, bytes):
        raise TypeError(f"{field_name} must be text path-compatible.")

    if not raw_path.strip() or "\x00" in raw_path:
        raise ValueError(f"{field_name} must be a valid path.")

    return Path(raw_path)


def _positive_duration(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be numeric.")

    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0:
        raise ValueError(f"{field_name} must be finite and positive.")
    return normalized


def _safe_text(value: str) -> str:
    if _SENSITIVE_TEXT.search(value):
        return _WITHHELD_VALUE
    return value


def _safe_path(value: Path) -> str:
    if value.is_absolute():
        return _ABSOLUTE_PATH

    rendered = value.as_posix()
    if _SENSITIVE_TEXT.search(rendered):
        return _WITHHELD_VALUE
    return rendered


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Validated configuration for the side-effect-free Doctor runtime."""

    application_name: str
    environment: str
    runtime_mode: RuntimeMode
    log_level: str
    data_directory: Path
    state_directory: Path
    diagnostics_output_directory: Path
    startup_timeout_seconds: float
    shutdown_timeout_seconds: float

    def __post_init__(self) -> None:
        from src.core.kernel.runtime import RuntimeMode

        application_name = _required_text(
            self.application_name,
            "application_name",
        )
        environment = _required_text(
            self.environment,
            "environment",
        ).casefold()
        log_level = _required_text(
            self.log_level,
            "log_level",
        ).upper()

        if environment not in KNOWN_ENVIRONMENTS:
            raise ValueError("environment is not supported.")
        if log_level not in KNOWN_LOG_LEVELS:
            raise ValueError("log_level is not supported.")
        if self.runtime_mode is not RuntimeMode.DOCTOR:
            raise ValueError("Only Doctor runtime mode is supported.")

        object.__setattr__(
            self,
            "application_name",
            application_name,
        )
        object.__setattr__(self, "environment", environment)
        object.__setattr__(self, "log_level", log_level)

        for field_name in (
            "data_directory",
            "state_directory",
            "diagnostics_output_directory",
        ):
            object.__setattr__(
                self,
                field_name,
                _path_value(getattr(self, field_name), field_name),
            )

        for field_name in (
            "startup_timeout_seconds",
            "shutdown_timeout_seconds",
        ):
            object.__setattr__(
                self,
                field_name,
                _positive_duration(
                    getattr(self, field_name),
                    field_name,
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic public data with sensitive paths withheld."""

        return {
            "application_name": _safe_text(self.application_name),
            "data_directory": _safe_path(self.data_directory),
            "diagnostics_output_directory": _safe_path(
                self.diagnostics_output_directory
            ),
            "environment": self.environment,
            "log_level": self.log_level,
            "runtime_mode": self.runtime_mode.value,
            "shutdown_timeout_seconds": self.shutdown_timeout_seconds,
            "startup_timeout_seconds": self.startup_timeout_seconds,
            "state_directory": _safe_path(self.state_directory),
        }

    def to_json(self) -> str:
        """Serialize deterministically without process environment data."""

        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )


__all__ = (
    "KNOWN_ENVIRONMENTS",
    "KNOWN_LOG_LEVELS",
    "RuntimeConfig",
)
