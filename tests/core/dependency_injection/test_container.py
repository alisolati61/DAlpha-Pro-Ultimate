from src.core.dependency_injection.container import Container

from src.core.dependency_injection.lifetime import ServiceLifetime


class IService:
    pass


class Service(IService):
    pass


def test_singleton():

    container = Container()

    container.register(IService, Service)

    a = container.resolve(IService)

    b = container.resolve(IService)

    assert a is b


def test_transient():

    container = Container()

    container.register(
        IService,
        Service,
        ServiceLifetime.TRANSIENT,
    )

    a = container.resolve(IService)

    b = container.resolve(IService)

    assert a is not b