import pytest

from src.core.lifecycle.lifecycle import LifecycleManager
from src.core.lifecycle.service import Service
from src.core.services.errors import LifecycleTransitionError
from src.core.services.models import ServiceDefinition, ServiceState


class DummyService(Service):
    def __init__(self):
        self.initialized = False
        self.started = False
        self.stopped = False

    def initialize(self):
        self.initialized = True

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


def test_lifecycle():
    manager = LifecycleManager()

    service = DummyService()

    manager.register("dummy", service)

    manager.initialize()
    manager.start()
    manager.stop()

    assert service.initialized
    assert service.started
    assert service.stopped
    assert manager.state_of("dummy") is ServiceState.STOPPED


def test_invalid_transitions_fail_closed():
    manager = LifecycleManager(
        (ServiceDefinition("dummy", DummyService()),)
    )

    with pytest.raises(LifecycleTransitionError):
        manager.start()

    manager.initialize()

    with pytest.raises(LifecycleTransitionError):
        manager.initialize()

    manager.start()
    manager.stop()
    manager.stop()

    with pytest.raises(LifecycleTransitionError):
        manager.register("late", DummyService())
