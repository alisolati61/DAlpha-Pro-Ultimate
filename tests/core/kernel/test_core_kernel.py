import pytest

from src.core.kernel.kernel import Kernel
from src.core.kernel.state import KernelState


def test_kernel_initial_state():
    kernel = Kernel()

    assert kernel.state == KernelState.CREATED


def test_kernel_initialize():
    kernel = Kernel()

    kernel.initialize()

    assert kernel.state == KernelState.INITIALIZED


def test_kernel_start():
    kernel = Kernel()

    kernel.initialize()
    kernel.start()

    assert kernel.state == KernelState.RUNNING


def test_kernel_stop():
    kernel = Kernel()

    kernel.initialize()
    kernel.start()
    kernel.stop()

    assert kernel.state == KernelState.STOPPED


def test_kernel_shutdown():
    kernel = Kernel()

    kernel.shutdown()

    assert kernel.state == KernelState.SHUTDOWN


def test_start_without_initialize():
    kernel = Kernel()

    with pytest.raises(RuntimeError):
        kernel.start()


def test_stop_without_running():
    kernel = Kernel()

    with pytest.raises(RuntimeError):
        kernel.stop()