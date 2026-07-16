from enum import Enum


class KernelState(Enum):
    CREATED = "created"
    INITIALIZED = "initialized"
    RUNNING = "running"
    STOPPED = "stopped"
    SHUTDOWN = "shutdown"