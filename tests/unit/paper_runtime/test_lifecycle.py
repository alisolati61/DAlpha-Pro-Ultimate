from __future__ import annotations

import pytest

from src.core.kernel.bootstrap import build_runtime
from src.paper_runtime import PaperExecutionCoordinator, PaperRuntimeError
from tests.unit.paper_runtime.test_coordinator import (
    account,
    event,
    intent,
    policy,
)


def test_operations_fail_closed_before_start_and_after_stop() -> None:
    service = PaperExecutionCoordinator(policy(), account())
    service.initialize()

    with pytest.raises(PaperRuntimeError):
        service.submit_intent(intent(), source_sequence=1)
    with pytest.raises(PaperRuntimeError):
        service.advance_market(event(1))

    service.start()
    submission = service.submit_intent(intent(), source_sequence=1)
    assert submission.order is not None
    checkpoint = service.export_checkpoint()
    service.stop()

    assert checkpoint.digest
    assert service.fills == ()
    assert service.events == ()
    assert service.account == account()
    with pytest.raises(PaperRuntimeError):
        service.submit_intent(intent(), source_sequence=1)
    with pytest.raises(PaperRuntimeError):
        service.advance_market(event(2))


def test_default_doctor_runtime_does_not_auto_register_paper_service() -> None:
    runtime = build_runtime()

    assert runtime.service_definitions == ()
    assert all(
        definition.service_id != "paper-execution"
        for definition in runtime.lifecycle_manager.definitions
    )
