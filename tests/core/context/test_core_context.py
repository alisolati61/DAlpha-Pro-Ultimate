from src.core.context.context_builder import ContextBuilder

from src.core.dependency_injection.container import Container

from src.core.registry.registry import Registry


def test_context():

    ctx = ContextBuilder.build()

    assert isinstance(ctx.container, Container)

    assert isinstance(ctx.registry, Registry)