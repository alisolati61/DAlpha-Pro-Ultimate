"""Manual read-only capture of canonical BingX VST canary inputs."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import time
from collections.abc import Callable, Sequence
from decimal import Decimal
from pathlib import Path
from typing import NoReturn

from src.risk.kill_switch import KillSwitch
from src.vst_runtime.canary_capture import (
    AsyncCanaryCaptureTransport,
    CanaryCaptureError,
    CanaryCaptureReport,
    capture_canary_inputs,
    create_async_canary_capture_transport,
)
from src.vst_runtime.models import VST_BASE_URLS, VstConfiguration
from src.vst_runtime.readiness import (
    AsyncReadinessTransport,
    create_async_readiness_transport,
)

CredentialProvider = Callable[[str], str]
ReadinessProvider = Callable[[VstConfiguration], AsyncReadinessTransport]
CaptureProvider = Callable[
    [VstConfiguration, str], AsyncCanaryCaptureTransport
]
Clock = Callable[[], int]


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        del message
        raise CanaryCaptureError("invalid_arguments") from None


def build_parser() -> argparse.ArgumentParser:
    parser = _SanitizedArgumentParser(
        description="Capture canonical read-only BingX VST canary inputs."
    )
    parser.add_argument(
        "--host",
        default="https://open-api-vst.bingx.com",
    )
    parser.add_argument("--configuration-version", default="canary-capture-v1")
    parser.add_argument("--maximum-clock-drift-ms", type=int, default=2_000)
    return parser


async def _run_capture(
    configuration: VstConfiguration,
    *,
    readiness_provider: ReadinessProvider,
    capture_provider: CaptureProvider,
    artifact_root: Path,
    clock_ms: Clock,
    local_kill_switch: KillSwitch,
) -> CanaryCaptureReport:
    return await capture_canary_inputs(
        configuration,
        readiness_provider=readiness_provider,
        capture_provider=capture_provider,
        local_kill_switch=local_kill_switch,
        artifact_root=artifact_root,
        clock_ms=clock_ms,
    )


def _validated_host(value: str) -> str:
    normalized = value.rstrip("/")
    if normalized not in VST_BASE_URLS:
        raise CanaryCaptureError("host_not_vst")
    return normalized


def _hidden_credential(
    provider: CredentialProvider,
    prompt: str,
) -> str:
    value = provider(prompt)
    if not isinstance(value, str) or not value.strip():
        raise CanaryCaptureError("credential_required")
    return value.strip()


def _default_artifact_root() -> Path:
    return Path(__file__).resolve().parents[1] / ".operator-artifacts"


def main(
    argv: Sequence[str] | None = None,
    *,
    credential_provider: CredentialProvider = getpass.getpass,
    readiness_provider: ReadinessProvider | None = None,
    capture_provider: CaptureProvider | None = None,
    output: Callable[[str], None] = print,
    clock_ms: Clock | None = None,
    artifact_root: Path | None = None,
) -> int:
    clock = clock_ms or (lambda: time.time_ns() // 1_000_000)
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
            maximum_order_notional=Decimal("10"),
            maximum_open_positions=1,
            maximum_session_loss=Decimal("10"),
            maximum_exposure=Decimal("10"),
            configuration_version=arguments.configuration_version,
            base_url=host,
            maximum_clock_drift_ms=arguments.maximum_clock_drift_ms,
        )
        report = asyncio.run(
            _run_capture(
                configuration,
                readiness_provider=(
                    create_async_readiness_transport
                    if readiness_provider is None
                    else readiness_provider
                ),
                capture_provider=(
                    create_async_canary_capture_transport
                    if capture_provider is None
                    else capture_provider
                ),
                artifact_root=artifact_root or _default_artifact_root(),
                clock_ms=clock,
                local_kill_switch=KillSwitch(),
            )
        )
    except SystemExit:
        raise
    except CanaryCaptureError as error:
        report = CanaryCaptureReport.blocked(
            error.reason_code,
            selected_host=error.selected_host,
        )
    except Exception:
        report = CanaryCaptureReport.blocked("capture_runtime_failed")
    output(report.to_json())
    return 0 if report.status == "CAPTURED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
