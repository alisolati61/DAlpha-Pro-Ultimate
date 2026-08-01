"""Prepare one canonical READY intent through the frozen local pipeline."""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import NoReturn

from src.execution_intent.models import IntentStatus
from src.vst_runtime.intent_preparation import (
    ARTIFACT_DIRECTORY_NAME,
    IntentPreparationError,
    IntentPreparationReport,
    prepare_demo_canary_intent,
)

ClockMs = Callable[[], int]
_MAX_INPUT_BYTES = 1_000_000


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        del message
        raise IntentPreparationError("invalid_arguments") from None


def build_parser() -> argparse.ArgumentParser:
    parser = _SanitizedArgumentParser(
        description=(
            "Create a canonical BingX VST READY intent from explicit local inputs."
        )
    )
    parser.add_argument("--market-input", required=True)
    parser.add_argument("--market-digest", required=True)
    parser.add_argument("--account-input", required=True)
    parser.add_argument("--account-digest", required=True)
    parser.add_argument("--constraints-input", required=True)
    parser.add_argument("--constraints-digest", required=True)
    parser.add_argument("--policy-input", required=True)
    parser.add_argument("--policy-digest", required=True)
    return parser


def _read_input(value: str) -> str:
    try:
        path = Path(value)
        if path.is_symlink() or not path.is_file():
            raise OSError
        if path.stat().st_size > _MAX_INPUT_BYTES:
            raise OSError
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeError):
        raise IntentPreparationError("input_unavailable") from None


def _default_artifact_directory() -> Path:
    return Path(__file__).resolve().parents[1] / ARTIFACT_DIRECTORY_NAME


def main(
    argv: Sequence[str] | None = None,
    *,
    output: Callable[[str], None] = print,
    artifact_directory: Path | None = None,
    clock_ms: ClockMs | None = None,
) -> int:
    clock = clock_ms or (lambda: time.time_ns() // 1_000_000)
    expected_failure = False
    try:
        arguments = build_parser().parse_args(argv)
        report = prepare_demo_canary_intent(
            market_json=_read_input(arguments.market_input),
            market_digest=arguments.market_digest,
            account_json=_read_input(arguments.account_input),
            account_digest=arguments.account_digest,
            constraints_json=_read_input(arguments.constraints_input),
            constraints_digest=arguments.constraints_digest,
            policy_json=_read_input(arguments.policy_input),
            policy_digest=arguments.policy_digest,
            artifact_directory=(
                _default_artifact_directory()
                if artifact_directory is None
                else artifact_directory
            ),
            clock_ms=clock,
        )
    except SystemExit:
        raise
    except IntentPreparationError as error:
        report = IntentPreparationReport.failure(error.reason_code)
        expected_failure = True
    except Exception:
        report = IntentPreparationReport.failure("intent_preparation_failed")
        output(report.to_json())
        return 1
    output(report.to_json())
    if expected_failure or report.status != IntentStatus.READY.value:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
