"""Safe manual composition through a persisted VST DemoOrderPlan."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, NoReturn

from scripts.bingx_vst_capture_canary_inputs import main as capture_main
from scripts.bingx_vst_demo_order import main as demo_main
from scripts.bingx_vst_prepare_intent import main as prepare_main
from src.vst_runtime.canary_capture import CANARY_CANDLE_INTERVAL_MS
from src.vst_runtime.demo_order import (
    DemoOrderPlan,
    load_canonical_demo_order_plan,
)
from src.vst_runtime.models import VST_BASE_URLS

CredentialProvider = Callable[[str], str]
Output = Callable[[str], None]
Runner = Callable[..., int]
ClockMs = Callable[[], int]
Sleeper = Callable[[float], None]
PlanLoader = Callable[[str], DemoOrderPlan]

_DEFAULT_HOST = "https://open-api-vst.bingx.pro"
_DEFAULT_ATTEMPTS = 3
_MAX_ATTEMPTS = 10
_CLOSE_SETTLEMENT_MS = 2_500
_MAX_ARTIFACT_BYTES = 1_000_000
_MIN_EXECUTION_TTL_MS = 90_000

_INTENT_RETRYABLE = frozenset(
    {
        "decision_hold",
        "canary_stop_distance_unavailable",
    }
)

_DRY_RUN_RETRYABLE = frozenset(
    {
        "marketable_limit_price",
        "passive_limit_unavailable",
    }
)

_CAPTURE_RETRYABLE = frozenset(
    {
        "stale_candles",
    }
)
_INPUT_FILES = frozenset(
    {
        "market-input.json",
        "account-input.json",
        "constraints-input.json",
        "policy-input.json",
    }
)


class RehearsalError(Exception):
    """Secret-free stable failure for the operator rehearsal wrapper."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        del message
        raise RehearsalError("invalid_arguments") from None


def build_parser() -> argparse.ArgumentParser:
    parser = _SanitizedArgumentParser(
        description=(
            "Capture, prepare, and dry-run one BingX VST canary "
            "without submission."
        )
    )
    parser.add_argument("--host", default=_DEFAULT_HOST)
    parser.add_argument(
        "--attempts",
        type=int,
        default=_DEFAULT_ATTEMPTS,
    )
    return parser


def _validated_host(value: str) -> str:
    normalized = value.rstrip("/")
    if normalized not in VST_BASE_URLS:
        raise RehearsalError("host_not_vst")
    return normalized


def _validated_attempts(value: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
        or value > _MAX_ATTEMPTS
    ):
        raise RehearsalError("invalid_attempt_limit")
    return value


def _hidden_credential(
    provider: CredentialProvider,
    prompt: str,
) -> str:
    value = provider(prompt)
    if not isinstance(value, str) or not value.strip():
        raise RehearsalError("credential_required")
    return value.strip()


def _parse_report(
    lines: list[str],
    stage: str,
    *,
    index: int = 0,
) -> dict[str, Any]:
    if len(lines) <= index:
        raise RehearsalError(f"{stage}_output_missing")
    try:
        value = json.loads(lines[index])
    except (TypeError, ValueError):
        raise RehearsalError(f"{stage}_output_invalid") from None
    if not isinstance(value, dict):
        raise RehearsalError(f"{stage}_output_invalid")
    return value


def _reason_codes(report: dict[str, Any]) -> set[str]:
    raw = report.get("reason_codes")
    if not isinstance(raw, list):
        return set()
    return {
        item
        for item in raw
        if isinstance(item, str) and item.strip()
    }


def _sha256_file(path: Path) -> str:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_size > _MAX_ARTIFACT_BYTES
    ):
        raise RehearsalError("artifact_invalid")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_capture(
    report: dict[str, Any],
) -> tuple[Path, dict[str, str]]:
    raw_directory = report.get("artifact_directory")
    raw_digests = report.get("input_digests")

    if (
        not isinstance(raw_directory, str)
        or not raw_directory.strip()
        or not isinstance(raw_digests, dict)
    ):
        raise RehearsalError("capture_artifact_invalid")

    directory = Path(raw_directory)

    if not directory.is_dir() or directory.is_symlink():
        raise RehearsalError("capture_artifact_invalid")

    if set(raw_digests) != _INPUT_FILES:
        raise RehearsalError("capture_digest_set_invalid")

    digests: dict[str, str] = {}

    for name in sorted(_INPUT_FILES):
        digest = raw_digests.get(name)

        if (
            not isinstance(digest, str)
            or len(digest) != 64
        ):
            raise RehearsalError("capture_digest_invalid")

        actual = _sha256_file(directory / name)

        if actual != digest.casefold():
            raise RehearsalError("capture_digest_mismatch")

        digests[name] = digest.casefold()

    return directory, digests


def _verify_intent(
    report: dict[str, Any],
) -> tuple[str, str]:
    raw_path = report.get("artifact_path")
    raw_digest = report.get("intent_digest")

    if (
        not isinstance(raw_path, str)
        or not raw_path.strip()
        or not isinstance(raw_digest, str)
        or len(raw_digest) != 64
    ):
        raise RehearsalError("intent_artifact_invalid")

    path = Path(raw_path)
    actual = _sha256_file(path)

    if actual != raw_digest.casefold():
        raise RehearsalError("intent_digest_mismatch")

    return raw_path, raw_digest.casefold()


def _wait_for_next_candle(
    *,
    clock_ms: ClockMs,
    sleeper: Sleeper,
    output: Output,
) -> None:
    current = clock_ms()
    next_boundary = (
        (current // CANARY_CANDLE_INTERVAL_MS) + 1
    ) * CANARY_CANDLE_INTERVAL_MS

    target = next_boundary + _CLOSE_SETTLEMENT_MS
    delay = max(0.0, (target - current) / 1_000)

    output(f"WAITING_NEXT_3M_SECONDS={delay:.1f}")
    sleeper(delay)


def _blocked(
    output: Output,
    *,
    stage: str,
    reason: str,
) -> int:
    output("REHEARSAL_STATUS=BLOCKED")
    output(f"BLOCKED_STAGE={stage}")
    output(f"REASON={reason}")
    output("ORDER_SUBMITTED=NO")
    output("EXECUTE_USED=NO")
    return 2


def _verify_plan(
    summary: dict[str, Any],
    *,
    intent_digest: str,
    host: str,
    clock_ms: ClockMs,
    plan_loader: PlanLoader,
) -> tuple[DemoOrderPlan, str, int]:
    raw_path = summary.get("plan_artifact_path")
    raw_digest = summary.get("plan_digest")
    raw_expiry = summary.get("expires_at_ms")

    if (
        not isinstance(raw_path, str)
        or not raw_path.strip()
        or not isinstance(raw_digest, str)
        or len(raw_digest) != 64
        or isinstance(raw_expiry, bool)
        or not isinstance(raw_expiry, int)
    ):
        raise RehearsalError("plan_summary_invalid")

    path = Path(raw_path)

    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_size > _MAX_ARTIFACT_BYTES
    ):
        raise RehearsalError("plan_artifact_invalid")

    expected_parent = (
        Path(".operator-artifacts") / "demo-order-plans"
    ).resolve()

    try:
        resolved = path.resolve()
    except OSError:
        raise RehearsalError("plan_artifact_invalid") from None

    if resolved.parent != expected_parent:
        raise RehearsalError("plan_artifact_path_invalid")

    digest = raw_digest.casefold()

    if path.name != f"{digest}.json":
        raise RehearsalError("plan_artifact_name_invalid")

    try:
        serialized = path.read_bytes().decode("utf-8")
        plan = plan_loader(serialized)
    except Exception:
        raise RehearsalError("plan_artifact_invalid") from None

    if plan.digest != digest:
        raise RehearsalError("plan_digest_mismatch")

    if plan.intent_digest != intent_digest:
        raise RehearsalError("plan_intent_mismatch")

    if plan.selected_host.rstrip("/") != host:
        raise RehearsalError("plan_host_mismatch")

    if plan.expires_at_ms != raw_expiry:
        raise RehearsalError("plan_expiry_mismatch")

    remaining_ms = plan.expires_at_ms - clock_ms()

    if remaining_ms <= 0:
        raise RehearsalError("plan_expired")

    return plan, raw_path, remaining_ms


def main(
    argv: Sequence[str] | None = None,
    *,
    credential_provider: CredentialProvider = getpass.getpass,
    output: Output = print,
    clock_ms: ClockMs | None = None,
    sleeper: Sleeper = time.sleep,
    capture_runner: Runner = capture_main,
    preparation_runner: Runner = prepare_main,
    demo_runner: Runner = demo_main,
    plan_loader: PlanLoader = load_canonical_demo_order_plan,
) -> int:
    clock = clock_ms or (
        lambda: time.time_ns() // 1_000_000
    )

    api_key = ""
    api_secret = ""

    try:
        arguments = build_parser().parse_args(argv)
        host = _validated_host(arguments.host)
        attempts = _validated_attempts(arguments.attempts)

        api_key = _hidden_credential(
            credential_provider,
            "BingX VST API key: ",
        )
        api_secret = _hidden_credential(
            credential_provider,
            "BingX VST API secret: ",
        )

        def credentials(prompt: str) -> str:
            lowered = prompt.casefold()
            if "key" in lowered:
                return api_key
            if "secret" in lowered:
                return api_secret
            raise RehearsalError("unexpected_credential_prompt")

        for attempt in range(1, attempts + 1):
            output("")
            output(f"=== ATTEMPT {attempt}/{attempts} ===")

            capture_lines: list[str] = []

            capture_code = capture_runner(
                ["--host", host],
                credential_provider=credentials,
                output=capture_lines.append,
            )

            capture = _parse_report(
                capture_lines,
                "capture",
            )
            capture_status = str(
                capture.get("status", "")
            )
            capture_reasons = _reason_codes(capture)

            output(f"CAPTURE_STATUS={capture_status}")
            output(
                "CAPTURE_REASON="
                + ",".join(sorted(capture_reasons))
            )

            if (
                capture_code != 0
                or capture_status != "CAPTURED"
            ):
                if (
                    capture_reasons & _CAPTURE_RETRYABLE
                    and attempt < attempts
                ):
                    _wait_for_next_candle(
                        clock_ms=clock,
                        sleeper=sleeper,
                        output=output,
                    )
                    continue

                reason = (
                    sorted(capture_reasons)[0]
                    if capture_reasons
                    else "capture_failed"
                )
                return _blocked(
                    output,
                    stage="CAPTURE",
                    reason=reason,
                )

            directory, digests = _verify_capture(capture)

            preparation_lines: list[str] = []

            preparation_code = preparation_runner(
                [
                    "--market-input",
                    str(directory / "market-input.json"),
                    "--market-digest",
                    digests["market-input.json"],
                    "--account-input",
                    str(directory / "account-input.json"),
                    "--account-digest",
                    digests["account-input.json"],
                    "--constraints-input",
                    str(directory / "constraints-input.json"),
                    "--constraints-digest",
                    digests["constraints-input.json"],
                    "--policy-input",
                    str(directory / "policy-input.json"),
                    "--policy-digest",
                    digests["policy-input.json"],
                ],
                output=preparation_lines.append,
            )

            preparation = _parse_report(
                preparation_lines,
                "preparation",
            )

            intent_status = str(
                preparation.get("status", "")
            )
            intent_reasons = _reason_codes(preparation)

            output(f"INTENT_STATUS={intent_status}")
            output(
                "INTENT_REASON="
                + ",".join(sorted(intent_reasons))
            )

            if (
                preparation_code != 0
                or intent_status != "READY"
            ):
                if (
                    intent_reasons & _INTENT_RETRYABLE
                    and attempt < attempts
                ):
                    _wait_for_next_candle(
                        clock_ms=clock,
                        sleeper=sleeper,
                        output=output,
                    )
                    continue

                reason = (
                    sorted(intent_reasons)[0]
                    if intent_reasons
                    else "intent_not_ready"
                )
                return _blocked(
                    output,
                    stage="INTENT_PREPARATION",
                    reason=reason,
                )

            intent_file, intent_digest = _verify_intent(
                preparation
            )

            demo_lines: list[str] = []

            demo_args = [
                "--intent-file",
                intent_file,
                "--intent-digest",
                intent_digest,
                "--host",
                host,
            ]

            demo_code = demo_runner(
                demo_args,
                credential_provider=credentials,
                output=demo_lines.append,
            )

            demo_report = _parse_report(
                demo_lines,
                "dry_run",
            )

            demo_status = str(
                demo_report.get("status", "")
            )
            demo_reasons = _reason_codes(demo_report)

            output(f"DRY_RUN_STATUS={demo_status}")
            output(
                "DRY_RUN_REASON="
                + ",".join(sorted(demo_reasons))
            )

            if (
                demo_code != 0
                or demo_status != "DRY_RUN_READY"
            ):
                if (
                    demo_reasons & _DRY_RUN_RETRYABLE
                    and attempt < attempts
                ):
                    _wait_for_next_candle(
                        clock_ms=clock,
                        sleeper=sleeper,
                        output=output,
                    )
                    continue

                reason = (
                    sorted(demo_reasons)[0]
                    if demo_reasons
                    else "dry_run_not_ready"
                )
                return _blocked(
                    output,
                    stage="DEMO_DRY_RUN",
                    reason=reason,
                )

            plan_summary = _parse_report(
                demo_lines,
                "plan_summary",
                index=1,
            )

            plan, plan_path, remaining_ms = _verify_plan(
                plan_summary,
                intent_digest=intent_digest,
                host=host,
                clock_ms=clock,
                plan_loader=plan_loader,
            )

            if remaining_ms < _MIN_EXECUTION_TTL_MS:
                output(
                    f"PLAN_TTL_TOO_LOW_MS={remaining_ms}"
                )

                if attempt < attempts:
                    _wait_for_next_candle(
                        clock_ms=clock,
                        sleeper=sleeper,
                        output=output,
                    )
                    continue

                return _blocked(
                    output,
                    stage="PLAN_TTL",
                    reason="insufficient_execution_ttl",
                )

            output("")
            output("========================================")
            output("REHEARSAL_STATUS=DRY_RUN_READY")
            output(f"SELECTED_HOST={plan.selected_host}")
            output(f"PLAN_SYMBOL={plan.symbol}")
            output(f"PLAN_SIDE={plan.side}")
            output(
                f"PLAN_POSITION_SIDE={plan.position_side}"
            )
            output(f"PLAN_QUANTITY={plan.quantity}")
            output(f"PLAN_LIMIT_PRICE={plan.limit_price}")
            output(f"PLAN_STOP_LOSS={plan.stop_loss}")
            output(f"PLAN_TAKE_PROFIT={plan.take_profit}")
            output(f"PLAN_NOTIONAL={plan.notional}")
            output(f"PLAN_LEVERAGE={plan.leverage}")
            output(f"INTENT_FILE={intent_file}")
            output(f"INTENT_DIGEST={intent_digest}")
            output(f"PLAN_ARTIFACT={plan_path}")
            output(f"PLAN_DIGEST={plan.digest}")
            output(
                f"PLAN_EXPIRES_AT_MS={plan.expires_at_ms}"
            )
            output(
                f"PLAN_TTL_REMAINING_MS={remaining_ms}"
            )
            output("PLAN_CANONICAL_VERIFY=PASS")
            output("ORDER_SUBMITTED=NO")
            output("EXECUTE_USED=NO")
            output("========================================")
            return 0

        output("REHEARSAL_STATUS=WATCH_EXHAUSTED")
        output("ORDER_SUBMITTED=NO")
        output("EXECUTE_USED=NO")
        return 2

    except RehearsalError as error:
        return _blocked(
            output,
            stage="VALIDATION",
            reason=error.reason_code,
        )
    except Exception:
        output("REHEARSAL_STATUS=FAILED")
        output("REASON=rehearsal_runtime_failed")
        output("ORDER_SUBMITTED=NO")
        output("EXECUTE_USED=NO")
        return 1
    finally:
        api_key = ""
        api_secret = ""


if __name__ == "__main__":
    raise SystemExit(main())
