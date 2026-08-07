"""Bounded foreground capture-to-dry-run watcher for BingX VST."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import math
import re
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import NoReturn, cast

from src.exchange.models import BingXBalance, BingXPosition
from src.execution_intent.models import IntentStatus
from src.risk.kill_switch import KillSwitch
from src.vst_runtime.canary_capture import (
    CAPTURE_DIRECTORY_NAME,
    AsyncCanaryCaptureTransport,
    CanaryCaptureError,
    CanaryCaptureReport,
    capture_canary_inputs,
    create_async_canary_capture_transport,
)
from src.vst_runtime.demo_order import (
    AsyncDemoOrderTransport,
    DemoCanaryError,
    DemoContractConstraints,
    DemoLeverageSnapshot,
    DemoOrderReport,
    DemoOrderStatus,
    DemoTopOfBook,
    build_demo_order_plan,
    dry_run_report,
    load_canonical_ready_intent,
)
from src.vst_runtime.demo_transport import create_async_demo_order_transport
from src.vst_runtime.intent_preparation import (
    ARTIFACT_DIRECTORY_NAME,
    IntentPreparationError,
    IntentPreparationReport,
    prepare_demo_canary_intent,
)
from src.vst_runtime.models import (
    VST_BASE_URLS,
    RemoteOrder,
    VstConfiguration,
)
from src.vst_runtime.readiness import (
    AsyncReadinessTransport,
    ReadinessStatus,
    check_vst_readiness,
    create_async_readiness_transport,
)

CredentialProvider = Callable[[str], str]
ReadinessProvider = Callable[[VstConfiguration], AsyncReadinessTransport]
CaptureProvider = Callable[
    [VstConfiguration, str], AsyncCanaryCaptureTransport
]
DemoTransportProvider = Callable[
    [VstConfiguration, str], AsyncDemoOrderTransport
]
Clock = Callable[[], int]
Monotonic = Callable[[], float]
Sleeper = Callable[[float], Awaitable[None]]
Output = Callable[[str], None]

_DEFAULT_ATTEMPTS = 5
_MAX_ATTEMPTS = 10
_CANDLE_INTERVAL_MS = 180_000
_CLOSE_SETTLEMENT_MS = 2_500
_MAX_SECONDS_PER_ATTEMPT = 185
_MAX_INPUT_BYTES = 1_000_000
_HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_CAPTURE_INPUTS = {
    "account-input.json": "account",
    "constraints-input.json": "constraints",
    "market-input.json": "market",
    "policy-input.json": "policy",
}


class CanaryWatchError(Exception):
    """Sanitized fail-closed error for the bounded manual watcher."""

    def __init__(self, reason_code: str) -> None:
        super().__init__("Canary watch failed.")
        self.reason_code = reason_code


class _DryRunFailure(DemoCanaryError):
    """Preserve only the sanitized host reached by the dry-run boundary."""

    def __init__(self, reason_code: str, selected_host: str | None) -> None:
        super().__init__(reason_code)
        self.selected_host = (
            selected_host.rstrip("/")
            if isinstance(selected_host, str)
            and selected_host.rstrip("/") in VST_BASE_URLS
            else None
        )


@dataclass(frozen=True, slots=True)
class CanaryWatchReport:
    """Secret-free final status for one bounded foreground watch."""

    status: str
    attempts: int
    selected_host: str | None
    reason_codes: tuple[str, ...]
    demo_report: DemoOrderReport | None = None

    def __post_init__(self) -> None:
        reasons = tuple(sorted(set(self.reason_codes)))
        if (
            not isinstance(self.attempts, int)
            or isinstance(self.attempts, bool)
            or self.attempts < 0
            or not reasons
        ):
            raise ValueError("watch report is invalid")
        if self.status == DemoOrderStatus.DRY_RUN_READY.value and (
            self.demo_report is None
            or self.demo_report.status is not DemoOrderStatus.DRY_RUN_READY
        ):
            raise ValueError("successful watch report is incomplete")
        object.__setattr__(self, "reason_codes", reasons)

    def to_dict(self) -> dict[str, object]:
        return {
            "attempts": self.attempts,
            "demo_report": (
                None
                if self.demo_report is None
                else json.loads(self.demo_report.to_json())
            ),
            "reason_codes": list(self.reason_codes),
            "selected_host": self.selected_host,
            "status": self.status,
        }

    def to_json(self) -> str:
        return _canonical(self.to_dict())

    @classmethod
    def blocked(
        cls,
        reason_code: str,
        *,
        attempts: int = 0,
        selected_host: str | None = None,
    ) -> CanaryWatchReport:
        return cls("BLOCKED", attempts, selected_host, (reason_code,))


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        del message
        raise CanaryWatchError("invalid_arguments") from None


class _ReadOnlyDemoTransport:
    """Hide every Demo write method from the watcher composition."""

    __slots__ = ("__transport",)

    def __init__(self, transport: AsyncDemoOrderTransport) -> None:
        self.__transport = transport

    @property
    def selected_host(self) -> str:
        return self.__transport.selected_host

    async def fetch_constraints(self, symbol: str) -> DemoContractConstraints:
        return await self.__transport.fetch_constraints(symbol)

    async def fetch_orderbook(self, symbol: str) -> DemoTopOfBook:
        return await self.__transport.fetch_orderbook(symbol)

    async def fetch_balances(self) -> Sequence[BingXBalance]:
        return await self.__transport.fetch_balances()

    async def fetch_positions(self, symbol: str) -> Sequence[BingXPosition]:
        return await self.__transport.fetch_positions(symbol)

    async def fetch_leverage(self, symbol: str) -> DemoLeverageSnapshot:
        return await self.__transport.fetch_leverage(symbol)

    async def fetch_position_mode(self) -> str:
        return await self.__transport.fetch_position_mode()

    async def query_order(
        self,
        symbol: str,
        client_order_id: str,
    ) -> RemoteOrder | None:
        return await self.__transport.query_order(symbol, client_order_id)

    async def fetch_open_orders(self, symbol: str) -> Sequence[RemoteOrder]:
        return await self.__transport.fetch_open_orders(symbol)

    async def fetch_recent_orders(self, symbol: str) -> Sequence[RemoteOrder]:
        return await self.__transport.fetch_recent_orders(symbol)

    async def close(self) -> None:
        await self.__transport.close()


def build_parser() -> argparse.ArgumentParser:
    parser = _SanitizedArgumentParser(
        description=(
            "Watch a bounded number of closed BTC-USDT VST candles and stop "
            "at the first read-only DRY_RUN_READY plan."
        )
    )
    parser.add_argument(
        "--host",
        default="https://open-api-vst.bingx.com",
    )
    parser.add_argument("--attempts", type=int, default=_DEFAULT_ATTEMPTS)
    return parser


async def watch_canary(
    configuration: VstConfiguration,
    *,
    max_attempts: int,
    readiness_provider: ReadinessProvider,
    capture_provider: CaptureProvider,
    demo_transport_provider: DemoTransportProvider,
    artifact_root: Path,
    clock_ms: Clock,
    monotonic: Monotonic,
    sleeper: Sleeper,
    progress: Output,
    local_kill_switch: KillSwitch,
) -> CanaryWatchReport:
    """Run a finite foreground loop over newly closed three-minute candles."""

    _attempt_limit(max_attempts)
    started = _monotonic_value(monotonic())
    deadline = started + (max_attempts * _MAX_SECONDS_PER_ATTEMPT)
    last_host: str | None = None
    last_retry_reason = "watch_attempt_limit_reached"
    last_sample_boundary_ms: int | None = None

    for attempt in range(1, max_attempts + 1):
        _emit_progress(
            progress,
            attempt,
            "WAITING",
            ("waiting_for_closed_candle",),
            last_host,
        )
        sample_boundary_ms = await _wait_for_closed_candle(
            clock_ms=clock_ms,
            monotonic=monotonic,
            sleeper=sleeper,
            deadline=deadline,
            after_boundary_ms=last_sample_boundary_ms,
        )
        if sample_boundary_ms is None:
            return CanaryWatchReport(
                "WATCH_EXHAUSTED",
                attempt - 1,
                last_host,
                ("watch_duration_exceeded",),
            )
        last_sample_boundary_ms = sample_boundary_ms
        remaining = deadline - _monotonic_value(monotonic())
        if remaining <= 0:
            return CanaryWatchReport(
                "WATCH_EXHAUSTED",
                attempt - 1,
                last_host,
                ("watch_duration_exceeded",),
            )
        try:
            capture = await asyncio.wait_for(
                capture_canary_inputs(
                    configuration,
                    readiness_provider=readiness_provider,
                    capture_provider=capture_provider,
                    local_kill_switch=local_kill_switch,
                    artifact_root=artifact_root,
                    clock_ms=clock_ms,
                    monotonic=monotonic,
                ),
                timeout=remaining,
            )
        except TimeoutError:
            return CanaryWatchReport(
                "WATCH_EXHAUSTED",
                attempt,
                last_host,
                ("watch_duration_exceeded",),
            )
        except CanaryCaptureError as error:
            return CanaryWatchReport.blocked(
                error.reason_code,
                attempts=attempt,
                selected_host=error.selected_host or last_host,
            )
        last_host = capture.selected_host
        if _monotonic_value(monotonic()) > deadline:
            return CanaryWatchReport(
                "WATCH_EXHAUSTED",
                attempt,
                last_host,
                ("watch_duration_exceeded",),
            )
        try:
            prepared = _prepare_capture(
                capture,
                artifact_root=artifact_root,
                clock_ms=clock_ms,
            )
        except IntentPreparationError as error:
            return CanaryWatchReport.blocked(
                error.reason_code,
                attempts=attempt,
                selected_host=last_host,
            )

        if (
            prepared.status == IntentStatus.NO_ACTION.value
            and prepared.reason_codes == ("decision_hold",)
        ):
            last_retry_reason = "decision_hold"
            _emit_progress(
                progress,
                attempt,
                prepared.status,
                prepared.reason_codes,
                last_host,
            )
            continue
        if prepared.status != IntentStatus.READY.value:
            return CanaryWatchReport(
                "BLOCKED",
                attempt,
                last_host,
                prepared.reason_codes,
            )
        remaining = deadline - _monotonic_value(monotonic())
        if remaining <= 0:
            return CanaryWatchReport(
                "WATCH_EXHAUSTED",
                attempt,
                last_host,
                ("watch_duration_exceeded",),
            )
        try:
            demo_report = await asyncio.wait_for(
                _dry_run_prepared(
                    configuration,
                    prepared,
                    artifact_root=artifact_root,
                    readiness_provider=readiness_provider,
                    demo_transport_provider=demo_transport_provider,
                    clock_ms=clock_ms,
                    monotonic=monotonic,
                ),
                timeout=remaining,
            )
        except TimeoutError:
            return CanaryWatchReport(
                "WATCH_EXHAUSTED",
                attempt,
                last_host,
                ("watch_duration_exceeded",),
            )
        except DemoCanaryError as error:
            error_host = getattr(error, "selected_host", None)
            if isinstance(error_host, str):
                last_host = error_host
            if error.reason_code == "marketable_limit_price":
                last_retry_reason = error.reason_code
                _emit_progress(
                    progress,
                    attempt,
                    "BLOCKED",
                    (error.reason_code,),
                    last_host,
                )
                continue
            return CanaryWatchReport.blocked(
                error.reason_code,
                attempts=attempt,
                selected_host=last_host,
            )
        if demo_report.status is not DemoOrderStatus.DRY_RUN_READY:
            return CanaryWatchReport(
                "BLOCKED",
                attempt,
                last_host,
                demo_report.reason_codes,
                demo_report,
            )
        return CanaryWatchReport(
            DemoOrderStatus.DRY_RUN_READY.value,
            attempt,
            demo_report.selected_host,
            ("dry_run_ready",),
            demo_report,
        )

    return CanaryWatchReport(
        "WATCH_EXHAUSTED",
        max_attempts,
        last_host,
        (last_retry_reason, "watch_attempt_limit_reached"),
    )


def _prepare_capture(
    capture: CanaryCaptureReport,
    *,
    artifact_root: Path,
    clock_ms: Clock,
) -> IntentPreparationReport:
    if (
        capture.status != "CAPTURED"
        or capture.capture_id is None
        or _HEX_DIGEST.fullmatch(capture.capture_id) is None
        or artifact_root.name != ARTIFACT_DIRECTORY_NAME
    ):
        raise IntentPreparationError("capture_artifact_unavailable")
    digests = dict(capture.input_digests)
    if set(digests) != set(_CAPTURE_INPUTS) or any(
        _HEX_DIGEST.fullmatch(value) is None for value in digests.values()
    ):
        raise IntentPreparationError("capture_artifact_unavailable")
    directory = artifact_root / CAPTURE_DIRECTORY_NAME / capture.capture_id
    contents = {
        key: _read_bounded_file(directory / filename, "capture_artifact_unavailable")
        for filename, key in _CAPTURE_INPUTS.items()
    }
    return prepare_demo_canary_intent(
        market_json=contents["market"],
        market_digest=digests["market-input.json"],
        account_json=contents["account"],
        account_digest=digests["account-input.json"],
        constraints_json=contents["constraints"],
        constraints_digest=digests["constraints-input.json"],
        policy_json=contents["policy"],
        policy_digest=digests["policy-input.json"],
        artifact_directory=artifact_root,
        clock_ms=clock_ms,
    )


async def _dry_run_prepared(
    configuration: VstConfiguration,
    prepared: IntentPreparationReport,
    *,
    artifact_root: Path,
    readiness_provider: ReadinessProvider,
    demo_transport_provider: DemoTransportProvider,
    clock_ms: Clock,
    monotonic: Monotonic,
) -> DemoOrderReport:
    if (
        prepared.status != IntentStatus.READY.value
        or prepared.artifact_path is None
        or prepared.intent_digest is None
    ):
        raise DemoCanaryError("ready_intent_unavailable")
    relative = Path(prepared.artifact_path)
    if (
        len(relative.parts) != 2
        or relative.parts[0] != ARTIFACT_DIRECTORY_NAME
        or relative.suffix != ".json"
        or _HEX_DIGEST.fullmatch(relative.stem) is None
    ):
        raise DemoCanaryError("ready_intent_unavailable")
    serialized = _read_bounded_file(
        artifact_root / relative.name,
        "ready_intent_unavailable",
    )
    intent, verified_digest = load_canonical_ready_intent(
        serialized,
        prepared.intent_digest,
    )
    readiness = await check_vst_readiness(
        configuration,
        readiness_provider(configuration),
        clock_ms=clock_ms,
        monotonic=monotonic,
    )
    if readiness.status is not ReadinessStatus.READY:
        reason = (
            f"readiness_{readiness.reason_codes[0]}"
            if readiness.reason_codes
            else "readiness_failed"
        )
        raise _DryRunFailure(reason, readiness.selected_host)
    concrete = demo_transport_provider(configuration, readiness.selected_host)
    read_only = _ReadOnlyDemoTransport(concrete)
    primary_failure = False
    try:
        try:
            plan = await build_demo_order_plan(
                intent,
                verified_digest,
                cast(AsyncDemoOrderTransport, read_only),
                clock_ms=clock_ms,
            )
        except DemoCanaryError as error:
            raise _DryRunFailure(
                error.reason_code,
                read_only.selected_host,
            ) from None
        return dry_run_report(plan, reported_at_ms=clock_ms())
    except BaseException:
        primary_failure = True
        raise
    finally:
        try:
            await read_only.close()
        except Exception:
            if not primary_failure:
                raise _DryRunFailure(
                    "transport_close_failed",
                    read_only.selected_host,
                ) from None


async def _wait_for_closed_candle(
    *,
    clock_ms: Clock,
    monotonic: Monotonic,
    sleeper: Sleeper,
    deadline: float,
    after_boundary_ms: int | None,
) -> int | None:
    now_ms = _clock_value(clock_ms())
    current_boundary_ms = (now_ms // _CANDLE_INTERVAL_MS) * _CANDLE_INTERVAL_MS
    if after_boundary_ms is None:
        target_boundary_ms = current_boundary_ms
    else:
        next_boundary_ms = after_boundary_ms + _CANDLE_INTERVAL_MS
        settled_boundary_ms = (
            max(0, now_ms - _CLOSE_SETTLEMENT_MS) // _CANDLE_INTERVAL_MS
        ) * _CANDLE_INTERVAL_MS
        target_boundary_ms = max(next_boundary_ms, settled_boundary_ms)
    target_ms = target_boundary_ms + _CLOSE_SETTLEMENT_MS
    delay = max(0.0, (target_ms - now_ms) / 1_000)
    remaining = deadline - _monotonic_value(monotonic())
    if delay > remaining:
        return None
    if delay:
        await sleeper(delay)
    if _monotonic_value(monotonic()) > deadline:
        return None
    return target_boundary_ms


def _read_bounded_file(path: Path, reason_code: str) -> str:
    try:
        if path.is_symlink() or not path.is_file():
            raise OSError
        if path.stat().st_size > _MAX_INPUT_BYTES:
            raise OSError
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeError):
        if reason_code == "ready_intent_unavailable":
            raise DemoCanaryError(reason_code) from None
        raise IntentPreparationError(reason_code) from None


def _emit_progress(
    output: Output,
    attempt: int,
    status: str,
    reason_codes: tuple[str, ...],
    selected_host: str | None,
) -> None:
    output(
        _canonical(
            {
                "attempt": attempt,
                "reason_codes": tuple(sorted(set(reason_codes))),
                "selected_host": selected_host,
                "status": status,
            }
        )
    )


def _validated_host(value: str) -> str:
    normalized = value.rstrip("/")
    if normalized not in VST_BASE_URLS:
        raise CanaryWatchError("host_not_vst")
    return normalized


def _attempt_limit(value: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= _MAX_ATTEMPTS
    ):
        raise CanaryWatchError("invalid_watch_attempts")
    return value


def _hidden_credential(provider: CredentialProvider, prompt: str) -> str:
    value = provider(prompt)
    if not isinstance(value, str) or not value.strip():
        raise CanaryWatchError("credential_required")
    return value.strip()


def _clock_value(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise CanaryWatchError("invalid_clock")
    return value


def _monotonic_value(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CanaryWatchError("invalid_clock")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise CanaryWatchError("invalid_clock")
    return result


def _default_artifact_root() -> Path:
    return Path(__file__).resolve().parents[1] / ARTIFACT_DIRECTORY_NAME


def _default_demo_transport_provider(
    configuration: VstConfiguration,
    selected_host: str,
) -> AsyncDemoOrderTransport:
    return create_async_demo_order_transport(
        configuration,
        selected_host=selected_host,
    )


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    credential_provider: CredentialProvider = getpass.getpass,
    readiness_provider: ReadinessProvider | None = None,
    capture_provider: CaptureProvider | None = None,
    demo_transport_provider: DemoTransportProvider | None = None,
    output: Output = print,
    clock_ms: Clock | None = None,
    monotonic: Monotonic = time.monotonic,
    sleeper: Sleeper = asyncio.sleep,
    artifact_root: Path | None = None,
) -> int:
    clock = clock_ms or (lambda: time.time_ns() // 1_000_000)
    try:
        arguments = build_parser().parse_args(argv)
        host = _validated_host(arguments.host)
        attempts = _attempt_limit(arguments.attempts)
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
            configuration_version="canary-watch-v1",
            base_url=host,
            maximum_clock_drift_ms=2_000,
        )
        report = asyncio.run(
            watch_canary(
                configuration,
                max_attempts=attempts,
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
                demo_transport_provider=(
                    _default_demo_transport_provider
                    if demo_transport_provider is None
                    else demo_transport_provider
                ),
                artifact_root=(
                    _default_artifact_root()
                    if artifact_root is None
                    else artifact_root
                ),
                clock_ms=clock,
                monotonic=monotonic,
                sleeper=sleeper,
                progress=output,
                local_kill_switch=KillSwitch(),
            )
        )
    except SystemExit:
        raise
    except KeyboardInterrupt:
        report = CanaryWatchReport.blocked("watch_interrupted")
    except CanaryWatchError as error:
        report = CanaryWatchReport.blocked(error.reason_code)
    except Exception:
        report = CanaryWatchReport.blocked("watch_runtime_failed")
        output(report.to_json())
        return 1
    output(report.to_json())
    return 0 if report.status == DemoOrderStatus.DRY_RUN_READY.value else 2


if __name__ == "__main__":
    raise SystemExit(main())
