from src.core.context.app_context import AppContext

from src.core.dependency_injection.container import Container

from src.core.registry.registry import Registry


class ContextBuilder:

    @staticmethod
    def build() -> AppContext:

        container = Container()

        registry = Registry()

        return AppContext(

            container=container,

            registry=registry,

        )