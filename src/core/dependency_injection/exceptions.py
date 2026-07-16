class DIError(Exception):
    """Base DI exception."""


class ServiceAlreadyRegistered(DIError):
    pass


class ServiceNotFound(DIError):
    pass