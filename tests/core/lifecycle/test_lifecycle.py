from src.core.lifecycle.lifecycle import LifecycleManager
from src.core.lifecycle.service import Service


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

    manager.register(service)

    manager.initialize()
    manager.start()
    manager.stop()

    assert service.initialized
    assert service.started
    assert service.stopped