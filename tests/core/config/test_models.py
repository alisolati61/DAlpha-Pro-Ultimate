"""Contract tests for immutable Doctor runtime configuration."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from math import inf, nan
from pathlib import Path

import pytest

from src.core.config.loader import load_runtime_config
from src.core.config.models import RuntimeConfig
from src.core.kernel.runtime import RuntimeMode


def test_defaults_are_typed_and_immutable() -> None:
    config = load_runtime_config()

    assert config.application_name == "Alpha Pro X Infinity"
    assert config.environment == "development"
    assert config.runtime_mode is RuntimeMode.DOCTOR
    assert config.log_level == "INFO"
    assert config.data_directory == Path("data")

    with pytest.raises(FrozenInstanceError):
        config.environment = "test"  # type: ignore[misc]


@pytest.mark.parametrize("application_name", ["", " ", "\n"])
def test_application_name_must_be_non_empty(
    application_name: str,
) -> None:
    from src.core.config.errors import ConfigurationValueError

    with pytest.raises(ConfigurationValueError):
        load_runtime_config(
            overrides={"application_name": application_name}
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("environment", "unknown"),
        ("log_level", "TRACE"),
        ("runtime_mode", "live"),
        ("runtime_mode", "paper"),
        ("runtime_mode", "demo"),
        ("runtime_mode", "dry-run"),
        ("runtime_mode", "vst"),
    ],
)
def test_closed_sets_reject_unknown_values(
    field_name: str,
    value: str,
) -> None:
    from src.core.config.errors import ConfigurationValueError

    with pytest.raises(ConfigurationValueError):
        load_runtime_config(overrides={field_name: value})


@pytest.mark.parametrize("value", [0, -1, True, nan, inf, -inf])
@pytest.mark.parametrize(
    "field_name",
    ["startup_timeout_seconds", "shutdown_timeout_seconds"],
)
def test_timeouts_must_be_finite_positive_numbers(
    field_name: str,
    value: object,
) -> None:
    from src.core.config.errors import ConfigurationValueError

    with pytest.raises(ConfigurationValueError):
        load_runtime_config(overrides={field_name: value})


@pytest.mark.parametrize(
    "field_name",
    [
        "data_directory",
        "state_directory",
        "diagnostics_output_directory",
    ],
)
def test_paths_must_be_non_empty_path_compatible(
    field_name: str,
) -> None:
    from src.core.config.errors import ConfigurationValueError

    with pytest.raises(ConfigurationValueError):
        load_runtime_config(overrides={field_name: ""})
    with pytest.raises(ConfigurationValueError):
        load_runtime_config(overrides={field_name: object()})


def test_runtime_config_requires_doctor_enum() -> None:
    defaults = load_runtime_config()

    with pytest.raises(ValueError, match="Doctor"):
        RuntimeConfig(
            application_name=defaults.application_name,
            environment=defaults.environment,
            runtime_mode="doctor",  # type: ignore[arg-type]
            log_level=defaults.log_level,
            data_directory=defaults.data_directory,
            state_directory=defaults.state_directory,
            diagnostics_output_directory=(
                defaults.diagnostics_output_directory
            ),
            startup_timeout_seconds=defaults.startup_timeout_seconds,
            shutdown_timeout_seconds=defaults.shutdown_timeout_seconds,
        )
