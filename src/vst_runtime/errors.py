"""Safe public failures for the controlled BingX VST boundary."""


class VstRuntimeError(Exception):
    """Base error whose message is safe to expose."""


class VstConfigurationError(VstRuntimeError):
    pass


class VstLifecycleError(VstRuntimeError):
    pass


class VstValidationError(VstRuntimeError):
    pass


class VstTransportError(VstRuntimeError):
    pass


class VstAmbiguousOutcome(VstTransportError):
    pass


class VstAuthenticationError(VstTransportError):
    pass


class VstRateLimitError(VstTransportError):
    pass


class VstSchemaError(VstTransportError):
    pass


__all__ = (
    "VstAmbiguousOutcome",
    "VstAuthenticationError",
    "VstConfigurationError",
    "VstLifecycleError",
    "VstRateLimitError",
    "VstRuntimeError",
    "VstSchemaError",
    "VstTransportError",
    "VstValidationError",
)
