from enum import Enum


class LifecycleState(Enum):
    CREATED = "created"
    INITIALIZED = "initialized"
    STARTED = "started"
    STOPPED = "stopped"