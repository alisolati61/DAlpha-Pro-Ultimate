"""Tests for explicit runtime configuration source precedence."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.config.errors import (
    ConfigurationFileError,
    ConfigurationSchemaError,
)
from src.core.config.loader import load_runtime_config


def test_loads_explicit_toml(tmp_path: Path) -> None:
    config_file = tmp_path / "runtime.toml"
    config_file.write_text(
        """
[runtime]
application_name = "Configured Alpha"
environment = "test"
runtime_mode = "doctor"
log_level = "warning"
data_directory = "local-data"
state_directory = "local-state"
diagnostics_output_directory = "reports"
startup_timeout_seconds = 2.5
shutdown_timeout_seconds = 3
""".strip(),
        encoding="utf-8",
    )

    config = load_runtime_config(config_file)

    assert config.application_name == "Configured Alpha"
    assert config.environment == "test"
    assert config.log_level == "WARNING"
    assert config.data_directory == Path("local-data")
    assert config.startup_timeout_seconds == 2.5


def test_precedence_is_defaults_file_environment_overrides(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "runtime.toml"
    config_file.write_text(
        """
[runtime]
environment = "test"
log_level = "debug"
startup_timeout_seconds = 2
""".strip(),
        encoding="utf-8",
    )

    config = load_runtime_config(
        config_file,
        environ={
            "UNRELATED": "ignored",
            "ALPHA_PRO_X_ENVIRONMENT": "staging",
            "ALPHA_PRO_X_LOG_LEVEL": "error",
        },
        overrides={"environment": "production"},
    )

    assert config.environment == "production"
    assert config.log_level == "ERROR"
    assert config.startup_timeout_seconds == 2
    assert config.state_directory == Path("state")


def test_injected_environment_mapping_converts_values() -> None:
    config = load_runtime_config(
        environ={
            "ALPHA_PRO_X_RUNTIME_MODE": "doctor",
            "ALPHA_PRO_X_STARTUP_TIMEOUT_SECONDS": "1.25",
            "ALPHA_PRO_X_DATA_DIRECTORY": "injected-data",
        }
    )

    assert config.startup_timeout_seconds == 1.25
    assert config.data_directory == Path("injected-data")


@pytest.mark.parametrize(
    "content",
    [
        "[unknown]\nvalue = 1",
        "[runtime]\nunknown = 1",
        "[runtime]\nenvironment = 'test'\n[extra]\nvalue = 1",
    ],
)
def test_unknown_sections_and_keys_are_rejected(
    tmp_path: Path,
    content: str,
) -> None:
    config_file = tmp_path / "runtime.toml"
    config_file.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigurationSchemaError):
        load_runtime_config(config_file)


def test_unknown_prefixed_environment_and_override_keys_fail() -> None:
    with pytest.raises(ConfigurationSchemaError):
        load_runtime_config(
            environ={"ALPHA_PRO_X_UNKNOWN": "value"}
        )

    with pytest.raises(ConfigurationSchemaError):
        load_runtime_config(overrides={"unknown": "value"})


def test_malformed_missing_and_unreadable_files_are_sanitized(
    tmp_path: Path,
) -> None:
    malformed = tmp_path / "secret-name.toml"
    malformed.write_text("[runtime\napi_key='hidden'", encoding="utf-8")

    for path in (malformed, tmp_path / "missing-secret.toml", tmp_path):
        with pytest.raises(ConfigurationFileError) as captured:
            load_runtime_config(path)

        message = str(captured.value).casefold()
        assert "secret-name" not in message
        assert "api_key" not in message
        assert str(tmp_path).casefold() not in message
