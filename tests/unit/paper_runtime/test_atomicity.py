from __future__ import annotations

import hashlib
import json

import pytest

from src.paper_runtime import (
    PaperCheckpoint,
    PaperExecutionCoordinator,
    PaperRuntimeError,
)
from src.paper_runtime.models import canonical_json
from tests.unit.paper_runtime.test_coordinator import (
    account,
    event,
    intent,
    policy,
)


class _FailOnce:
    def __init__(self, stage: str) -> None:
        self.stage = stage
        self.armed = True

    def __call__(self, stage: str) -> None:
        if self.armed and stage == self.stage:
            raise RuntimeError(r"C:\private\.env API_SECRET=hidden")


def _running(hook: _FailOnce | None = None) -> PaperExecutionCoordinator:
    service = PaperExecutionCoordinator(
        policy(cap="10"), account(), commit_hook=hook
    )
    service.initialize()
    service.start()
    return service


def test_order_registration_failure_rolls_back_idempotency_and_balance() -> None:
    hook = _FailOnce("order_registration")
    service = _running(hook)
    before = service.export_checkpoint()

    with pytest.raises(
        PaperRuntimeError, match="Paper execution"
    ) as captured:
        service.submit_intent(intent(), source_sequence=1)

    assert captured.value.__cause__ is None
    assert "private" not in str(captured.value)
    assert "SECRET" not in str(captured.value)
    assert service.export_checkpoint() == before
    assert service.account == account()
    assert service.events == ()
    hook.armed = False
    retry = service.submit_intent(intent(), source_sequence=1)
    assert retry.accepted
    assert retry.order is not None


@pytest.mark.parametrize(
    "stage",
    (
        "fill_recording",
        "position_update",
        "balance_update",
        "portfolio_update",
        "protective_activation",
    ),
)
def test_fill_commit_stage_failure_restores_exact_state_and_cursor(
    stage: str,
) -> None:
    hook = _FailOnce(stage)
    service = _running(hook)
    submission = service.submit_intent(intent(), source_sequence=1)
    assert submission.order is not None
    before = service.export_checkpoint()

    with pytest.raises(PaperRuntimeError, match="Paper execution"):
        service.advance_market(event(2))

    assert service.export_checkpoint() == before
    assert service.fills == ()
    assert service.position("BTCUSDT").quantity == 0
    hook.armed = False
    service.advance_market(event(2))
    assert service.order(submission.order.order_id).filled_quantity > 0


def test_checkpoint_restore_hook_failure_restores_target_exactly() -> None:
    source = _running()
    source.submit_intent(intent(), source_sequence=1)
    source.advance_market(event(2))
    checkpoint = source.export_checkpoint()

    hook = _FailOnce("checkpoint_restore")
    target = _running(hook)
    before = target.export_checkpoint()
    with pytest.raises(PaperRuntimeError, match="Paper execution"):
        target.restore_checkpoint(checkpoint)

    assert target.export_checkpoint() == before
    hook.armed = False
    target.restore_checkpoint(checkpoint)
    assert target.export_checkpoint() == checkpoint


def test_semantically_invalid_but_digest_valid_checkpoint_changes_nothing() -> None:
    service = _running()
    service.submit_intent(intent(), source_sequence=1)
    before = service.export_checkpoint()
    payload = json.loads(before.payload_json)
    payload["account"]["balance"] = "1"
    payload_json = canonical_json(payload)
    digest = hashlib.sha256(
        f"{before.policy_id}:{before.version}:{payload_json}".encode()
    ).hexdigest()
    corrupted = PaperCheckpoint(
        before.policy_id, before.version, payload_json, digest
    )

    with pytest.raises(PaperRuntimeError, match="Paper execution"):
        service.restore_checkpoint(corrupted)

    assert service.export_checkpoint() == before


def test_checkpoint_rejects_same_identifier_with_different_policy() -> None:
    source = PaperExecutionCoordinator(policy(cap="1"), account())
    source.initialize()
    source.start()
    checkpoint = source.export_checkpoint()
    target = PaperExecutionCoordinator(policy(cap="10"), account())
    target.initialize()
    target.start()
    before = target.export_checkpoint()

    with pytest.raises(PaperRuntimeError, match="Paper execution"):
        target.restore_checkpoint(checkpoint)

    assert target.export_checkpoint() == before
