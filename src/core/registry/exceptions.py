class RegistryError(Exception):
    """Base Registry exception."""


class AlreadyRegisteredError(RegistryError):
    """Raised when a key already exists."""


class NotRegisteredError(RegistryError):
    """Raised when key is not found."""