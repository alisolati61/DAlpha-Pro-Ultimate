from src.core.kernel.kernel import Kernel


def bootstrap() -> Kernel:
    """
    Bootstrap the application.

    Future responsibilities:

    - Load configuration
    - Register services
    - Initialize plugins
    - Initialize EventBus
    - Initialize Dependency Container
    """

    kernel = Kernel()
    kernel.initialize()

    return kernel