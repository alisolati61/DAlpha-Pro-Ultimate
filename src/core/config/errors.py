"""Sanitized exceptions for explicit runtime configuration failures."""

from __future__ import annotations


class ConfigurationError(Exception):
    """Base class whose public text never includes underlying details."""

    public_message = "Runtime configuration is invalid."

    def __init__(self) -> None:
        super().__init__(self.public_message)


class ConfigurationFileError(ConfigurationError):
    """An explicitly requested configuration file could not be loaded."""

    public_message = "Runtime configuration file could not be loaded."


class ConfigurationSchemaError(ConfigurationError):
    """The configuration contains unsupported fields or sections."""

    public_message = "Runtime configuration schema is invalid."


class ConfigurationValueError(ConfigurationError):
    """A supported configuration value failed validation."""

    public_message = "Runtime configuration values are invalid."


__all__ = (
    "ConfigurationError",
    "ConfigurationFileError",
    "ConfigurationSchemaError",
    "ConfigurationValueError",
)
