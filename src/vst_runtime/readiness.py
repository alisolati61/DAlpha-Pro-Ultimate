"""Async-native, read-only readiness verification for BingX VST."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Callable, Protocol, runtime_checkable

from src.exchange.bingx_client import (
    BingXHttpClient,
    BingXTransportError,
    classify_transport_exception,
)
from src.exchange.exceptions import (
    AuthenticationError,
    ExchangeError,
    NetworkError,
    RateLimitError,
)
from src.exchange.models import BingXBalance, BingXPosition

from .models import VstConfiguration, canonical

Clock = Callable[[], int]
MonotonicClock = Callable[[], float]
_PRIMARY_VST_HOST = "https://open-api-vst.bingx.com"
_SIGNATURE_ERROR_CODES = frozenset({"100004", "100413"})
_INVALID_ENDPOINT_CODES = frozenset({"100404"})
_MAX_SERVER_TIME_SAMPLES = 3
_EARLY_RELIABLE_RTT_MS = 250


class ReadinessStatus(str, Enum):
    READY = "READY"
    FAILED = "FAILED"


@runtime_checkable
class AsyncReadinessTransport(Protocol):
    """The complete network surface available to readiness."""

    async def fetch_server_time(self) -> int: ...

    async def fetch_balance(self) -> Sequence[BingXBalance]: ...

    async def fetch_positions(self) -> Sequence[BingXPosition]: ...

    async def close(self) -> None: ...

    @property
    def selected_host(self) -> str: ...


class BingXAsyncReadinessAdapter:
    """Read-only composition wrapper over the frozen BingX HTTP client."""

    __slots__ = ("_client",)

    def __init__(self, client: BingXHttpClient) -> None:
        if not isinstance(client, BingXHttpClient):
            raise TypeError("client must be a BingXHttpClient")
        self._client = client

    async def fetch_server_time(self) -> int:
        return await self._client.get_server_time()

    async def fetch_balance(self) -> Sequence[BingXBalance]:
        return await self._client.get_balance()

    async def fetch_positions(self) -> Sequence[BingXPosition]:
        return await self._client.get_positions()

    async def close(self) -> None:
        await self._client.close()

    @property
    def selected_host(self) -> str:
        return self._client.last_attempted_base_url


def create_async_readiness_transport(
    configuration: VstConfiguration,
) -> AsyncReadinessTransport:
    """Compose the frozen concrete client after VST configuration validation."""

    # Omitting an explicit base URL for the primary host preserves the frozen
    # client's official .com -> .pro network/timeout fallback policy.
    selected_base_url = (
        None if configuration.base_url == _PRIMARY_VST_HOST else configuration.base_url
    )
    client = BingXHttpClient(
        api_key=configuration.api_key,
        api_secret=configuration.api_secret,
        demo_mode=True,
        base_url=selected_base_url,
        recv_window=configuration.recv_window_ms,
        timeout=configuration.timeout_seconds,
    )
    return BingXAsyncReadinessAdapter(client)


@dataclass(frozen=True, slots=True)
class VstReadinessReport:
    status: ReadinessStatus
    policy_id: str
    selected_host: str
    server_timestamp_ms: int | None
    local_timestamp_ms: int
    clock_drift_ms: int | None
    round_trip_ms: int | None
    signing_check: bool
    authenticated_account_read: bool
    balance_read: bool
    positions_read: bool
    balance_count: int
    position_count: int
    reason_codes: tuple[str, ...]
    recommended_action: str
    digest: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", tuple(sorted(set(self.reason_codes))))
        expected = hashlib.sha256(
            self.to_json(include_digest=False).encode()
        ).hexdigest()
        if self.digest and self.digest != expected:
            raise ValueError("readiness report digest is invalid")
        object.__setattr__(self, "digest", expected)

    def to_dict(self, *, include_digest: bool = True) -> dict[str, object]:
        value = asdict(self)
        value["status"] = self.status.value
        if not include_digest:
            value.pop("digest")
        return value

    def to_json(self, *, include_digest: bool = True) -> str:
        return canonical(self.to_dict(include_digest=include_digest))


@dataclass(frozen=True, slots=True)
class _ClockSample:
    server_time_ms: int
    midpoint_ms: int
    drift_ms: int
    round_trip_ms: int
    selected_host: str


async def check_vst_readiness(
    configuration: VstConfiguration,
    transport: AsyncReadinessTransport,
    *,
    clock_ms: Clock,
    monotonic: MonotonicClock = time.monotonic,
) -> VstReadinessReport:
    """Perform exactly server-time, balance, and position reads."""

    local_time = 0
    server_time: int | None = None
    drift: int | None = None
    round_trip: int | None = None
    selected_host = configuration.base_url
    authenticated = False
    balance_ok = False
    positions_ok = False
    balance_count = 0
    position_count = 0
    reasons: set[str] = set()
    samples: list[_ClockSample] = []
    sample_failures: list[str] = []

    try:
        for _attempt in range(_MAX_SERVER_TIME_SAMPLES):
            try:
                sample = await _collect_clock_sample(
                    transport,
                    clock_ms=clock_ms,
                    monotonic=monotonic,
                )
            except Exception as error:
                selected_host = transport.selected_host
                sample_failures.append(_failure_reason(error))
                continue
            samples.append(sample)
            if sample.round_trip_ms <= _EARLY_RELIABLE_RTT_MS:
                break

        valid_samples = [
            sample
            for sample in samples
            if sample.round_trip_ms <= configuration.maximum_clock_drift_ms
        ]
        if valid_samples:
            chosen = min(valid_samples, key=lambda item: item.round_trip_ms)
            server_time = chosen.server_time_ms
            local_time = chosen.midpoint_ms
            drift = chosen.drift_ms
            round_trip = chosen.round_trip_ms
            selected_host = chosen.selected_host
        elif samples:
            observed = min(samples, key=lambda item: item.round_trip_ms)
            server_time = observed.server_time_ms
            local_time = observed.midpoint_ms
            drift = observed.drift_ms
            round_trip = observed.round_trip_ms
            selected_host = observed.selected_host
            reasons.add("clock_sample_unreliable")
        elif sample_failures:
            reasons.add(sample_failures[0])
        else:
            reasons.add("readiness_check_failed")

        if (
            not reasons
            and drift is not None
            and (drift > configuration.maximum_clock_drift_ms)
        ):
            reasons.add("clock_drift_exceeded")

        if not reasons:
            balances = tuple(await transport.fetch_balance())
            if not balances or any(
                not isinstance(item, BingXBalance) for item in balances
            ):
                raise _ReadinessSchemaError("invalid_balance_schema")
            authenticated = True
            balance_ok = True
            balance_count = len(balances)

            positions = tuple(await transport.fetch_positions())
            if any(not isinstance(item, BingXPosition) for item in positions):
                raise _ReadinessSchemaError("invalid_positions_schema")
            positions_ok = True
            position_count = len(positions)
    except Exception as error:
        reasons.add(_failure_reason(error))
    finally:
        try:
            await transport.close()
        except Exception:
            reasons.add("transport_close_failed")

    passed = not reasons and authenticated and balance_ok and positions_ok
    return VstReadinessReport(
        status=ReadinessStatus.READY if passed else ReadinessStatus.FAILED,
        policy_id=configuration.policy_id,
        selected_host=selected_host,
        server_timestamp_ms=server_time,
        local_timestamp_ms=local_time,
        clock_drift_ms=drift,
        round_trip_ms=round_trip,
        signing_check=server_time is not None,
        authenticated_account_read=authenticated,
        balance_read=balance_ok,
        positions_read=positions_ok,
        balance_count=balance_count,
        position_count=position_count,
        reason_codes=("ready",) if passed else tuple(reasons),
        recommended_action="none" if passed else _recommended_action(reasons),
    )


def _recommended_action(reasons: set[str]) -> str:
    if "clock_sample_unreliable" in reasons:
        return "retry_read_only_readiness"
    if "clock_drift_exceeded" in reasons:
        return "synchronize_system_clock"
    if reasons & {"authentication_rejected", "signature_rejected"}:
        return "verify_vst_credentials"
    if any(reason.startswith("invalid_") for reason in reasons):
        return "verify_bingx_vst_api_compatibility"
    return "retry_read_only_readiness"


class _ReadinessSchemaError(Exception):
    def __init__(self, reason_code: str) -> None:
        super().__init__()
        self.reason_code = reason_code


async def _collect_clock_sample(
    transport: AsyncReadinessTransport,
    *,
    clock_ms: Clock,
    monotonic: MonotonicClock,
) -> _ClockSample:
    wall_before = clock_ms()
    monotonic_before = monotonic()
    server_time = await transport.fetch_server_time()
    monotonic_after = monotonic()
    wall_after = clock_ms()
    if isinstance(server_time, bool) or not isinstance(server_time, int):
        raise _ReadinessSchemaError("invalid_server_time_schema")
    midpoint = (wall_before + wall_after) // 2
    round_trip = max(
        0,
        round((monotonic_after - monotonic_before) * 1_000),
    )
    return _ClockSample(
        server_time_ms=server_time,
        midpoint_ms=midpoint,
        drift_ms=abs(midpoint - server_time),
        round_trip_ms=round_trip,
        selected_host=transport.selected_host,
    )


def _failure_reason(error: BaseException) -> str:
    if isinstance(error, AuthenticationError):
        return (
            "signature_rejected"
            if error.error_code in _SIGNATURE_ERROR_CODES
            else "authentication_rejected"
        )
    if isinstance(error, RateLimitError):
        return "rate_limit_failed"
    if isinstance(error, NetworkError):
        return _network_reason(error)
    if isinstance(error, ExchangeError):
        return (
            "invalid_endpoint"
            if error.error_code in _INVALID_ENDPOINT_CODES
            else "http_status_failure"
        )
    if isinstance(error, (TimeoutError, OSError)):
        return _network_reason(error)
    if isinstance(error, _ReadinessSchemaError):
        return error.reason_code
    if isinstance(error, (TypeError, ValueError)):
        return "invalid_server_time_schema"
    return "readiness_check_failed"


def _network_reason(error: BaseException) -> str:
    if isinstance(error, BingXTransportError):
        return error.reason_code
    return classify_transport_exception(
        error,
        attempted_host="unknown",
    ).reason_code


__all__ = (
    "AsyncReadinessTransport",
    "BingXAsyncReadinessAdapter",
    "ReadinessStatus",
    "VstReadinessReport",
    "check_vst_readiness",
    "create_async_readiness_transport",
)
