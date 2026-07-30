"""Explicit manual entry point for read-only BingX VST readiness."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import time
from collections.abc import Callable, Sequence
from decimal import Decimal

from src.vst_runtime.models import VST_BASE_URLS, VstConfiguration
from src.vst_runtime.readiness import (
    AsyncReadinessTransport,
    ReadinessStatus,
    check_vst_readiness,
    create_async_readiness_transport,
)

CredentialProvider = Callable[[str], str]
TransportProvider = Callable[[VstConfiguration], AsyncReadinessTransport]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run read-only BingX VST readiness checks."
    )
    parser.add_argument(
        "--host",
        default="https://open-api-vst.bingx.com",
    )
    parser.add_argument("--configuration-version", default="manual-v1")
    parser.add_argument("--maximum-clock-drift-ms", type=int, default=2_000)
    return parser


async def _run_readiness(
    configuration: VstConfiguration,
    transport_provider: TransportProvider,
    clock_ms: Callable[[], int],
) -> tuple[int, str]:
    transport = transport_provider(configuration)
    report = await check_vst_readiness(
        configuration,
        transport,
        clock_ms=clock_ms,
    )
    return (
        0 if report.status is ReadinessStatus.READY else 1,
        report.to_json(),
    )


def _validated_host(value: str) -> str:
    normalized = value.rstrip("/")
    if normalized not in VST_BASE_URLS:
        raise ValueError("host is not an allowlisted VST host")
    return normalized


def _hidden_credential(
    credential_provider: CredentialProvider,
    prompt: str,
) -> str:
    value = credential_provider(prompt)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("credential is required")
    return value.strip()


def main(
    argv: Sequence[str] | None = None,
    *,
    credential_provider: CredentialProvider = getpass.getpass,
    transport_provider: TransportProvider | None = None,
    output: Callable[[str], None] = print,
    clock_ms: Callable[[], int] | None = None,
) -> int:
    try:
        arguments = build_parser().parse_args(argv)
        host = _validated_host(arguments.host)
        api_key = _hidden_credential(
            credential_provider,
            "BingX VST API key: ",
        )
        api_secret = _hidden_credential(
            credential_provider,
            "BingX VST API secret: ",
        )
        configuration = VstConfiguration(
            api_key=api_key,
            api_secret=api_secret,
            symbols=frozenset({"BTC-USDT"}),
            maximum_order_notional=Decimal("1"),
            maximum_open_positions=1,
            maximum_session_loss=Decimal("1"),
            configuration_version=arguments.configuration_version,
            base_url=host,
            maximum_clock_drift_ms=arguments.maximum_clock_drift_ms,
        )
        selected_provider = (
            create_async_readiness_transport
            if transport_provider is None
            else transport_provider
        )
        code, rendered = asyncio.run(
            _run_readiness(
                configuration,
                selected_provider,
                clock_ms or (lambda: time.time_ns() // 1_000_000),
            )
        )
        output(rendered)
        return code
    except SystemExit:
        raise
    except Exception:
        output(
            json.dumps(
                {
                    "reason_codes": ["configuration_or_readiness_invalid"],
                    "recommended_action": "verify_vst_configuration",
                    "status": "FAILED",
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
