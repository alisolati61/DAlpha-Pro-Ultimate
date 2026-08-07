from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import scripts.bingx_vst_rehearse as rehearsal


def test_parser_has_no_submission_flag() -> None:
    with pytest.raises(
        rehearsal.RehearsalError,
        match="invalid_arguments",
    ):
        rehearsal.build_parser().parse_args(
            ["--execute"]
        )


def test_hold_retry_reaches_verified_dry_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    output: list[str] = []
    sleeps: list[float] = []
    prepare_calls = 0
    capture_calls = 0
    demo_argv: list[list[str]] = []
    intent_digest = ""

    def credential_provider(prompt: str) -> str:
        if "key" in prompt.casefold():
            return "test-key"
        return "test-secret"

    def capture_runner(
        argv: list[str],
        **kwargs: Any,
    ) -> int:
        del argv
        nonlocal capture_calls
        capture_calls += 1

        directory = (
            Path(".operator-artifacts")
            / "canary-inputs"
            / f"capture-{capture_calls}"
        )
        directory.mkdir(parents=True)

        digests: dict[str, str] = {}

        for name in (
            "market-input.json",
            "account-input.json",
            "constraints-input.json",
            "policy-input.json",
        ):
            path = directory / name
            content = f'{{"name":"{name}"}}'
            path.write_text(content, encoding="utf-8")
            digests[name] = hashlib.sha256(
                content.encode()
            ).hexdigest()

        kwargs["output"](
            json.dumps(
                {
                    "artifact_directory": str(directory),
                    "input_digests": digests,
                    "reason_codes": ["capture_complete"],
                    "status": "CAPTURED",
                }
            )
        )
        return 0

    def preparation_runner(
        argv: list[str],
        **kwargs: Any,
    ) -> int:
        del argv
        nonlocal prepare_calls
        nonlocal intent_digest
        prepare_calls += 1

        if prepare_calls == 1:
            kwargs["output"](
                json.dumps(
                    {
                        "reason_codes": ["decision_hold"],
                        "status": "NO_ACTION",
                    }
                )
            )
            return 2

        path = Path(".operator-artifacts") / "intent.json"
        content = '{"intent":"ready"}'
        path.parent.mkdir(exist_ok=True)
        path.write_text(content, encoding="utf-8")

        intent_digest = hashlib.sha256(
            content.encode()
        ).hexdigest()

        kwargs["output"](
            json.dumps(
                {
                    "artifact_path": str(path),
                    "intent_digest": intent_digest,
                    "reason_codes": ["intent_ready"],
                    "status": "READY",
                }
            )
        )
        return 0

    plan_digest = "7" * 64

    def demo_runner(
        argv: list[str],
        **kwargs: Any,
    ) -> int:
        demo_argv.append(list(argv))

        plan_directory = (
            Path(".operator-artifacts")
            / "demo-order-plans"
        )
        plan_directory.mkdir(parents=True, exist_ok=True)

        plan_path = plan_directory / f"{plan_digest}.json"
        plan_path.write_text("{}", encoding="utf-8")

        kwargs["output"](
            json.dumps(
                {
                    "reason_codes": ["dry_run_ready"],
                    "status": "DRY_RUN_READY",
                }
            )
        )
        kwargs["output"](
            json.dumps(
                {
                    "expires_at_ms": 1_000_000,
                    "plan_artifact_path": str(plan_path),
                    "plan_digest": plan_digest,
                }
            )
        )
        return 0

    def plan_loader(serialized: str) -> Any:
        assert serialized == "{}"
        return SimpleNamespace(
            digest=plan_digest,
            intent_digest=intent_digest,
            selected_host=(
                "https://open-api-vst.bingx.pro"
            ),
            expires_at_ms=1_000_000,
            symbol="BTC-USDT",
            side="SELL",
            position_side="SHORT",
            quantity="0.0001",
            limit_price="64000",
            stop_loss="64640",
            take_profit="62720",
            notional="6.4",
            leverage=2,
        )

    result = rehearsal.main(
        ["--attempts", "3"],
        credential_provider=credential_provider,
        output=output.append,
        clock_ms=lambda: 10_000,
        sleeper=sleeps.append,
        capture_runner=capture_runner,
        preparation_runner=preparation_runner,
        demo_runner=demo_runner,
        plan_loader=plan_loader,
    )

    assert result == 0
    assert capture_calls == 2
    assert prepare_calls == 2
    assert len(sleeps) == 1
    assert demo_argv
    assert all(
        "--execute" not in arguments
        for arguments in demo_argv
    )
    assert "REHEARSAL_STATUS=DRY_RUN_READY" in output
    assert "PLAN_CANONICAL_VERIFY=PASS" in output
    assert "ORDER_SUBMITTED=NO" in output
    assert "EXECUTE_USED=NO" in output


def test_operator_launches_rehearsal_as_repo_module() -> None:
    root = Path(__file__).resolve().parents[3]
    operator = (
        root / "tools" / "operator.ps1"
    ).read_text(encoding="utf-8")

    assert '$Rehearsal = Join-Path' not in operator
    assert '"scripts.bingx_vst_rehearse"' in operator

    rehearsal_block = operator.split(
        'if ($Action -eq "rehearse") {',
        1,
    )[1].split(
        'Write-Host "Alpha Pro VST operator"',
        1,
    )[0]

    assert '"-m"' in rehearsal_block
