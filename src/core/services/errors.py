"""Sanitized failures for the local runtime service graph."""

from __future__ import annotations


class ServiceGraphError(Exception):
    """Base graph failure with stable, non-sensitive public text."""

    public_message = "Local service graph is invalid."

    def __init__(self) -> None:
        super().__init__(self.public_message)


class InvalidServiceDefinitionError(ServiceGraphError):
    """A service definition does not satisfy the public contract."""

    public_message = "Local service definition is invalid."


class DuplicateServiceError(ServiceGraphError):
    """More than one definition uses the same service ID."""

    public_message = "Local service IDs must be unique."


class MissingServiceDependencyError(ServiceGraphError):
    """A dependency does not identify a registered service."""

    public_message = "Local service dependency is not registered."


class ServiceDependencyCycleError(ServiceGraphError):
    """The dependency graph cannot be resolved acyclically."""

    public_message = "Local service dependency cycle detected."


class LifecycleTransitionError(ServiceGraphError):
    """A lifecycle operation was requested from an invalid state."""

    public_message = "Local service lifecycle transition is invalid."


__all__ = (
    "DuplicateServiceError",
    "InvalidServiceDefinitionError",
    "LifecycleTransitionError",
    "MissingServiceDependencyError",
    "ServiceDependencyCycleError",
    "ServiceGraphError",
)
