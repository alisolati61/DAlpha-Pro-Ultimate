"""Explicit manual entry point for one controlled BingX VST Demo canary."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import hmac
import json
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import NoReturn

from src.vst_runtime.demo_order import (
    AsyncDemoOrderTransport,
    DemoCanaryError,
    DemoCanaryPolicy,
    DemoOrderPlan,
    DemoOrderReport,
    DemoOrderStatus,
    blocked_report,
    build_demo_order_plan,
    dry_run_report,
    execute_demo_order_plan,
    failed_report,
    load_canonical_demo_order_plan,
    load_canonical_ready_intent,
)
from src.vst_runtime.demo_transport import create_async_demo_order_transport
from src.vst_runtime.intent_preparation import ARTIFACT_DIRECTORY_NAME
from src.vst_runtime.models import VST_BASE_URLS, VstConfiguration
from src.vst_runtime.readiness import (
    AsyncReadinessTransport,
    ReadinessStatus,
    check_vst_readiness,
    create_async_readiness_transport,
)

CredentialProvider = Callable[[str], str]
ConfirmationProvider = Callable[[str], str]
ReadinessProvider = Callable[[VstConfiguration], AsyncReadinessTransport]
DemoTransportProvider = Callable[
    [VstConfiguration, str], AsyncDemoOrderTransport
]
Clock = Callable[[], int]
Output = Callable[[str], None]

_PLAN_ARTIFACT_DIRECTORY_NAME = "demo-order-plans"


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        del message
        raise DemoCanaryError("invalid_arguments") from None


def build_parser() -> argparse.ArgumentParser:
    parser = _SanitizedArgumentParser(
        description="Build or execute one manual BingX VST Demo order canary."
    )
    parser.add_argument("--intent-file", required=True)
    parser.add_argument("--intent-digest", required=True)
    parser.add_argument(
        "--host",
        default="https://open-api-vst.bingx.com",
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--plan-file")
    parser.add_argument("--plan-digest")
    return parser


async def _run_canary(
    configuration: VstConfiguration,
    serialized_intent: str,
    intent_digest: str,
    *,
    execute: bool,
    plan_file: str | None,
    approved_plan_digest: str | None,
    readiness_provider: ReadinessProvider,
    demo_transport_provider: DemoTransportProvider,
    confirmation_provider: ConfirmationProvider,
    clock_ms: Clock,
    artifact_root: Path,
) -> tuple[DemoOrderReport, str | None]:
    """Return the report and, only for a successful dry run, its artifact path."""

    intent, verified_intent_digest = load_canonical_ready_intent(
        serialized_intent,
        intent_digest,
    )
    readiness_transport = readiness_provider(configuration)
    readiness = await check_vst_readiness(
        configuration,
        readiness_transport,
        clock_ms=clock_ms,
    )
    if readiness.status is not ReadinessStatus.READY:
        reason = (
            f"readiness_{readiness.reason_codes[0]}"
            if readiness.reason_codes
            else "readiness_failed"
        )
        return blocked_report(reason, reported_at_ms=clock_ms()), None

    if execute:
        if plan_file is None:
            return blocked_report(
                "plan_file_required", reported_at_ms=clock_ms()
            ), None
        try:
            plan = load_canonical_demo_order_plan(_read_plan_file(plan_file))
        except DemoCanaryError as error:
            return blocked_report(
                error.reason_code, reported_at_ms=clock_ms()
            ), None
        if (
            plan.intent_id != intent.intent_id
            or plan.intent_digest != verified_intent_digest
        ):
            return blocked_report(
                "plan_intent_mismatch", reported_at_ms=clock_ms(), plan=plan
            ), None
        if plan.selected_host != readiness.selected_host:
            return blocked_report(
                "plan_host_mismatch", reported_at_ms=clock_ms(), plan=plan
            ), None
        if clock_ms() > plan.expires_at_ms:
            return blocked_report(
                "plan_expired", reported_at_ms=clock_ms(), plan=plan
            ), None
        if approved_plan_digest is None:
            return blocked_report(
                "approved_plan_digest_required",
                reported_at_ms=clock_ms(),
                plan=plan,
            ), None
        if not hmac.compare_digest(
            plan.digest,
            approved_plan_digest.strip().casefold(),
        ):
            return blocked_report(
                "plan_digest_mismatch", reported_at_ms=clock_ms(), plan=plan
            ), None
        transport = demo_transport_provider(configuration, readiness.selected_host)
        try:
            typed = confirmation_provider(
                f"Type SUBMIT {plan.client_order_id} to authorize this VST order: "
            )
            if not isinstance(typed, str):
                typed = ""
            report = await execute_demo_order_plan(
                plan,
                transport,
                approved_plan_digest=approved_plan_digest,
                typed_confirmation=typed,
                clock_ms=clock_ms,
            )
            return report, None
        finally:
            await transport.close()

    transport = demo_transport_provider(configuration, readiness.selected_host)
    try:
        plan = await build_demo_order_plan(
            intent,
            verified_intent_digest,
            transport,
            clock_ms=clock_ms,
        )
        try:
            artifact_path = _write_plan_artifact(artifact_root, plan)
        except DemoCanaryError as error:
            return blocked_report(
                error.reason_code, reported_at_ms=clock_ms(), plan=plan
            ), None
        return dry_run_report(plan, reported_at_ms=clock_ms()), artifact_path
    finally:
        await transport.close()


def _validated_host(value: str) -> str:
    normalized = value.rstrip("/")
    if normalized not in VST_BASE_URLS:
        raise DemoCanaryError("host_not_vst")
    return normalized


def _hidden_credential(
    provider: CredentialProvider,
    prompt: str,
) -> str:
    value = provider(prompt)
    if not isinstance(value, str) or not value.strip():
        raise DemoCanaryError("credential_required")
    return value.strip()


def _read_intent(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise DemoCanaryError("intent_input_unavailable") from None


def _read_plan_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise DemoCanaryError("invalid_plan_schema") from None


def _write_plan_artifact(directory: Path, plan: DemoOrderPlan) -> str:
    if not isinstance(directory, Path) or directory.name != ARTIFACT_DIRECTORY_NAME:
        raise DemoCanaryError("plan_artifact_directory_invalid")
    plan_directory = directory / _PLAN_ARTIFACT_DIRECTORY_NAME
    for path in (directory, plan_directory):
        if path.exists() and (not path.is_dir() or path.is_symlink()):
            raise DemoCanaryError("plan_artifact_directory_invalid")
    content = plan.to_json().encode("utf-8")
    try:
        directory.mkdir(exist_ok=True)
        plan_directory.mkdir(exist_ok=True)
        path = plan_directory / f"{plan.digest}.json"
        if path.exists():
            if (
                not path.is_file()
                or path.is_symlink()
                or path.read_bytes() != content
            ):
                raise DemoCanaryError("plan_artifact_conflict")
        else:
            with path.open("xb") as stream:
                stream.write(content)
    except DemoCanaryError:
        raise
    except OSError:
        raise DemoCanaryError("plan_artifact_write_failed") from None
    return (
        f"{ARTIFACT_DIRECTORY_NAME}/{_PLAN_ARTIFACT_DIRECTORY_NAME}/"
        f"{plan.digest}.json"
    )


def _plan_artifact_summary(
    plan: DemoOrderPlan,
    artifact_path: str,
    *,
    intent_file: str,
    intent_digest: str,
    host: str,
) -> str:
    next_command = (
        "python scripts/bingx_vst_demo_order.py "
        f'--intent-file "{intent_file}" '
        f"--intent-digest {intent_digest} "
        f"--host {host} "
        "--execute "
        f'--plan-file "{artifact_path}" '
        f"--plan-digest {plan.digest}"
    )
    return _canonical(
        {
            "expires_at_ms": plan.expires_at_ms,
            "next_execute_command": next_command,
            "plan_artifact_path": artifact_path,
            "plan_digest": plan.digest,
        }
    )


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _default_artifacts_root() -> Path:
    return Path(__file__).resolve().parents[1] / ARTIFACT_DIRECTORY_NAME


def _default_demo_transport_provider(
    configuration: VstConfiguration,
    selected_host: str,
) -> AsyncDemoOrderTransport:
    return create_async_demo_order_transport(
        configuration,
        selected_host=selected_host,
    )


def _exit_code(report: DemoOrderReport) -> int:
    if report.status in {
        DemoOrderStatus.DRY_RUN_READY,
        DemoOrderStatus.RECONCILED,
    }:
        return 0
    if report.status is DemoOrderStatus.BLOCKED:
        return 2
    return 1


def main(
    argv: Sequence[str] | None = None,
    *,
    credential_provider: CredentialProvider = getpass.getpass,
    confirmation_provider: ConfirmationProvider = input,
    readiness_provider: ReadinessProvider | None = None,
    demo_transport_provider: DemoTransportProvider | None = None,
    output: Output = print,
    clock_ms: Clock | None = None,
    artifact_root: Path | None = None,
) -> int:
    clock = clock_ms or (lambda: time.time_ns() // 1_000_000)
    artifact_path: str | None = None
    try:
        arguments = build_parser().parse_args(argv)
        host = _validated_host(arguments.host)
        if arguments.execute and not arguments.plan_digest:
            raise DemoCanaryError("approved_plan_digest_required")
        if arguments.execute and not arguments.plan_file:
            raise DemoCanaryError("plan_file_required")
        serialized_intent = _read_intent(arguments.intent_file)
        intent, _verified_digest = load_canonical_ready_intent(
            serialized_intent,
            arguments.intent_digest,
        )
        assert intent.symbol is not None
        api_key = _hidden_credential(
            credential_provider,
            "BingX VST API key: ",
        )
        api_secret = _hidden_credential(
            credential_provider,
            "BingX VST API secret: ",
        )
        policy = DemoCanaryPolicy()
        configuration = VstConfiguration(
            api_key=api_key,
            api_secret=api_secret,
            symbols=frozenset({intent.symbol}),
            maximum_order_notional=policy.maximum_notional,
            maximum_open_positions=1,
            maximum_session_loss=policy.maximum_notional,
            maximum_exposure=policy.maximum_notional,
            configuration_version=policy.version,
            base_url=host,
        )
        report, artifact_path = asyncio.run(
            _run_canary(
                configuration,
                serialized_intent,
                arguments.intent_digest,
                execute=arguments.execute,
                plan_file=arguments.plan_file,
                approved_plan_digest=arguments.plan_digest,
                readiness_provider=(
                    create_async_readiness_transport
                    if readiness_provider is None
                    else readiness_provider
                ),
                demo_transport_provider=(
                    _default_demo_transport_provider
                    if demo_transport_provider is None
                    else demo_transport_provider
                ),
                confirmation_provider=confirmation_provider,
                clock_ms=clock,
                artifact_root=(
                    _default_artifacts_root()
                    if artifact_root is None
                    else artifact_root
                ),
            )
        )
    except SystemExit:
        raise
    except DemoCanaryError as error:
        report = blocked_report(error.reason_code, reported_at_ms=clock())
    except Exception:
        report = failed_report("canary_runtime_failed", reported_at_ms=clock())
    output(report.to_json())
    if artifact_path is not None and report.plan is not None:
        output(
            _plan_artifact_summary(
                report.plan,
                artifact_path,
                intent_file=arguments.intent_file,
                intent_digest=arguments.intent_digest,
                host=host,
            )
        )
    return _exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
