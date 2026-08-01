"""Explicit manual entry point for one controlled BingX VST Demo canary."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import hmac
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import NoReturn

from src.vst_runtime.demo_order import (
    AsyncDemoOrderTransport,
    DemoCanaryError,
    DemoCanaryPolicy,
    DemoOrderReport,
    DemoOrderStatus,
    blocked_report,
    build_demo_order_plan,
    dry_run_report,
    execute_demo_order_plan,
    failed_report,
    load_canonical_ready_intent,
)
from src.vst_runtime.demo_transport import create_async_demo_order_transport
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
    parser.add_argument("--plan-digest")
    return parser


async def _run_canary(
    configuration: VstConfiguration,
    serialized_intent: str,
    intent_digest: str,
    *,
    execute: bool,
    approved_plan_digest: str | None,
    readiness_provider: ReadinessProvider,
    demo_transport_provider: DemoTransportProvider,
    confirmation_provider: ConfirmationProvider,
    clock_ms: Clock,
) -> DemoOrderReport:
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
        return blocked_report(reason, reported_at_ms=clock_ms())

    transport = demo_transport_provider(configuration, readiness.selected_host)
    try:
        plan = await build_demo_order_plan(
            intent,
            verified_intent_digest,
            transport,
            clock_ms=clock_ms,
        )
        if not execute:
            return dry_run_report(plan, reported_at_ms=clock_ms())
        if approved_plan_digest is None:
            return blocked_report(
                "approved_plan_digest_required",
                reported_at_ms=clock_ms(),
                plan=plan,
            )
        if not hmac.compare_digest(
            plan.digest,
            approved_plan_digest.strip().casefold(),
        ):
            return blocked_report(
                "plan_digest_mismatch",
                reported_at_ms=clock_ms(),
                plan=plan,
            )
        typed = confirmation_provider(
            f"Type SUBMIT {plan.client_order_id} to authorize this VST order: "
        )
        if not isinstance(typed, str):
            typed = ""
        return await execute_demo_order_plan(
            plan,
            transport,
            approved_plan_digest=approved_plan_digest,
            typed_confirmation=typed,
            clock_ms=clock_ms,
        )
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
    output: Callable[[str], None] = print,
    clock_ms: Clock | None = None,
) -> int:
    clock = clock_ms or (lambda: time.time_ns() // 1_000_000)
    try:
        arguments = build_parser().parse_args(argv)
        host = _validated_host(arguments.host)
        if arguments.execute and not arguments.plan_digest:
            raise DemoCanaryError("approved_plan_digest_required")
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
        report = asyncio.run(
            _run_canary(
                configuration,
                serialized_intent,
                arguments.intent_digest,
                execute=arguments.execute,
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
            )
        )
    except SystemExit:
        raise
    except DemoCanaryError as error:
        report = blocked_report(error.reason_code, reported_at_ms=clock())
    except Exception:
        report = failed_report("canary_runtime_failed", reported_at_ms=clock())
    output(report.to_json())
    return _exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
