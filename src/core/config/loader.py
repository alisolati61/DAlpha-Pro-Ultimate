"""Explicit, side-effect-free loading for Doctor runtime configuration."""

from __future__ import annotations

import math
import os
import tomllib
from collections.abc import Mapping
from pathlib import Path

from src.core.config.errors import (
    ConfigurationFileError,
    ConfigurationSchemaError,
    ConfigurationValueError,
)
from src.core.config.models import RuntimeConfig

_RUNTIME_SECTION = "runtime"
_FIELDS = frozenset(
    {
        "application_name",
        "environment",
        "runtime_mode",
        "log_level",
        "data_directory",
        "state_directory",
        "diagnostics_output_directory",
        "startup_timeout_seconds",
        "shutdown_timeout_seconds",
    }
)
_ENVIRONMENT_FIELDS = {
    f"ALPHA_PRO_X_{field.upper()}": field
    for field in _FIELDS
}
_DEFAULTS: dict[str, object] = {
    "application_name": "Alpha Pro X Infinity",
    "environment": "development",
    "runtime_mode": "doctor",
    "log_level": "INFO",
    "data_directory": Path("data"),
    "state_directory": Path("state"),
    "diagnostics_output_directory": Path("diagnostics"),
    "startup_timeout_seconds": 10.0,
    "shutdown_timeout_seconds": 10.0,
}


def _explicit_file(
    config_path: str | os.PathLike[str],
) -> dict[str, object]:
    try:
        raw_path = os.fspath(config_path)
        if isinstance(raw_path, bytes):
            raise TypeError
        with open(raw_path, "rb") as stream:
            parsed = tomllib.load(stream)
    except (OSError, TypeError, ValueError, tomllib.TOMLDecodeError) as error:
        raise ConfigurationFileError from error

    if set(parsed) != {_RUNTIME_SECTION}:
        raise ConfigurationSchemaError

    runtime_section = parsed[_RUNTIME_SECTION]
    if not isinstance(runtime_section, dict):
        raise ConfigurationSchemaError
    if not set(runtime_section).issubset(_FIELDS):
        raise ConfigurationSchemaError

    return dict(runtime_section)


def _environment_values(
    environ: Mapping[str, str] | None,
) -> dict[str, object]:
    if environ is None:
        return {}
    if not isinstance(environ, Mapping):
        raise ConfigurationValueError

    values: dict[str, object] = {}
    for key, value in environ.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ConfigurationValueError
        if not key.startswith("ALPHA_PRO_X_"):
            continue
        if key not in _ENVIRONMENT_FIELDS:
            raise ConfigurationSchemaError
        values[_ENVIRONMENT_FIELDS[key]] = value
    return values


def _override_values(
    overrides: Mapping[str, object] | None,
) -> dict[str, object]:
    if overrides is None:
        return {}
    if not isinstance(overrides, Mapping):
        raise ConfigurationValueError
    if not set(overrides).issubset(_FIELDS):
        raise ConfigurationSchemaError
    return dict(overrides)


def _runtime_mode(value: object) -> object:
    from src.core.kernel.runtime import RuntimeMode

    if isinstance(value, RuntimeMode):
        return value
    if not isinstance(value, str):
        raise ConfigurationValueError

    try:
        return RuntimeMode(value.strip().casefold())
    except ValueError as error:
        raise ConfigurationValueError from error


def _timeout(value: object) -> object:
    if isinstance(value, str):
        try:
            converted = float(value)
        except ValueError as error:
            raise ConfigurationValueError from error
        if not math.isfinite(converted):
            raise ConfigurationValueError
        return converted
    return value


def load_runtime_config(
    config_path: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
    overrides: Mapping[str, object] | None = None,
) -> RuntimeConfig:
    """Load explicit sources in increasing precedence order."""

    values = dict(_DEFAULTS)
    if config_path is not None:
        values.update(_explicit_file(config_path))
    values.update(_environment_values(environ))
    values.update(_override_values(overrides))

    values["runtime_mode"] = _runtime_mode(values["runtime_mode"])
    for field_name in (
        "startup_timeout_seconds",
        "shutdown_timeout_seconds",
    ):
        values[field_name] = _timeout(values[field_name])

    try:
        return RuntimeConfig(**values)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ConfigurationValueError from error


__all__ = ("load_runtime_config",)
