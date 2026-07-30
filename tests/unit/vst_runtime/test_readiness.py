from __future__ import annotations

import ast
import getpass
import importlib
import inspect
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

import scripts.bingx_vst_readiness as command
from src.exchange.bingx_client import BingXHttpClient
from src.exchange.exceptions import AuthenticationError, ExchangeError, NetworkError
from src.exchange.models import (
    BingXBalance,
    BingXPosition,
    BingXPositionSide,
)
from src.vst_runtime.models import VstConfiguration
from src.vst_runtime.readiness import (
    BingXAsyncReadinessAdapter,
    ReadinessStatus,
    check_vst_readiness,
    create_async_readiness_transport,
)

NOW = 10_000


def configuration(**changes: Any) -> VstConfiguration:
    values: dict[str, Any] = {
        "api_key": "read-key",
        "api_secret": "read-secret",
        "symbols": frozenset({"BTC-USDT"}),
        "maximum_order_notional": Decimal("1"),
        "maximum_open_positions": 1,
        "maximum_session_loss": Decimal("1"),
        "configuration_version": "readiness-v1",
    }
    values.update(changes)
    return VstConfiguration(**values)


def balance() -> BingXBalance:
    return BingXBalance("VST", 100, 0, 100, 90, 90)


def position() -> BingXPosition:
    return BingXPosition(
        "BTC-USDT",
        BingXPositionSide.LONG,
        1,
        100,
        100,
        0,
        0,
        1,
        "CROSSED",
    )


class AsyncReadOnlyFake:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.server_time: object = NOW
        self.balances: object = (balance(),)
        self.positions: object = (position(),)
        self.failure: Exception | None = None
        self.closed = False
        self.selected_host = "https://open-api-vst.bingx.pro"
        self.server_times: list[object] = []
        self.selected_hosts: list[str] = []

    async def fetch_server_time(self) -> int:
        self.calls.append("fetch_server_time")
        if self.failure:
            raise self.failure
        if self.server_times:
            value = self.server_times.pop(0)
            if self.selected_hosts:
                self.selected_host = self.selected_hosts.pop(0)
            return value  # type: ignore[return-value]
        return self.server_time  # type: ignore[return-value]

    async def fetch_balance(self) -> tuple[BingXBalance, ...]:
        self.calls.append("fetch_balance")
        if self.failure:
            raise self.failure
        return self.balances  # type: ignore[return-value]

    async def fetch_positions(self) -> tuple[BingXPosition, ...]:
        self.calls.append("fetch_positions")
        if self.failure:
            raise self.failure
        return self.positions  # type: ignore[return-value]

    async def close(self) -> None:
        self.calls.append("close")
        self.closed = True


@pytest.mark.asyncio
async def test_success_is_canonical_secret_free_and_read_only() -> None:
    fake = AsyncReadOnlyFake()
    report = await check_vst_readiness(configuration(), fake, clock_ms=lambda: NOW)
    assert report.status is ReadinessStatus.READY
    assert report.selected_host == "https://open-api-vst.bingx.pro"
    assert report.round_trip_ms == 0
    assert report.balance_count == report.position_count == 1
    assert fake.calls == [
        "fetch_server_time",
        "fetch_balance",
        "fetch_positions",
        "close",
    ]
    assert report.to_json() == report.to_json()
    assert report.digest
    rendered = repr(report) + report.to_json()
    assert "read-key" not in rendered
    assert "read-secret" not in rendered
    assert '"balance":' not in report.to_json()
    assert '"positions":' not in report.to_json()


def test_command_parser_has_no_api_key_argument() -> None:
    arguments = command.build_parser().parse_args([])
    option_strings = {
        option
        for action in command.build_parser()._actions
        for option in action.option_strings
    }
    assert not hasattr(arguments, "api_key")
    assert "--api-key" not in option_strings
    assert (
        inspect.signature(command.main).parameters["credential_provider"].default
        is getpass.getpass
    )


def test_production_host_fails_before_credential_or_network_use() -> None:
    calls: list[str] = []
    output: list[str] = []

    def credential_provider(_: str) -> str:
        calls.append("credential")
        return "must-not-be-read"

    def transport_provider(_: VstConfiguration) -> AsyncReadOnlyFake:
        calls.append("network")
        return AsyncReadOnlyFake()

    assert command.main(
        ["--host", "https://open-api.bingx.com"],
        credential_provider=credential_provider,
        transport_provider=transport_provider,
        output=output.append,
    )
    assert calls == []
    assert "configuration_or_readiness_invalid" in output[0]


@pytest.mark.parametrize(
    "credentials",
    [
        (" ",),
        ("hidden-key", " "),
    ],
)
def test_blank_credentials_fail_before_client_creation(
    credentials: tuple[str, ...],
) -> None:
    values = iter(credentials)
    output: list[str] = []
    transport_calls: list[str] = []

    def transport_provider(_: VstConfiguration) -> AsyncReadOnlyFake:
        transport_calls.append("create")
        return AsyncReadOnlyFake()

    assert command.main(
        [],
        credential_provider=lambda _: next(values),
        transport_provider=transport_provider,
        output=output.append,
    )
    assert transport_calls == []
    assert "configuration_or_readiness_invalid" in output[0]
    assert all(value not in output[0] for value in credentials if value.strip())


def test_no_argument_cli_hides_both_credentials_and_sanitizes_output() -> None:
    prompts: list[str] = []
    output: list[str] = []
    fake = AsyncReadOnlyFake()
    created: list[VstConfiguration] = []

    def credential_provider(prompt: str) -> str:
        prompts.append(prompt)
        return {
            "BingX VST API key: ": "hidden-key",
            "BingX VST API secret: ": "hidden-secret",
        }[prompt]

    def transport_provider(
        configuration: VstConfiguration,
    ) -> AsyncReadOnlyFake:
        created.append(configuration)
        return fake

    code = command.main(
        [],
        credential_provider=credential_provider,
        transport_provider=transport_provider,
        output=output.append,
        clock_ms=lambda: NOW,
    )
    assert code == 0
    assert prompts == [
        "BingX VST API key: ",
        "BingX VST API secret: ",
    ]
    assert len(created) == 1
    assert fake.closed
    assert "hidden-secret" not in "".join(output)
    assert "hidden-key" not in "".join(output)
    assert "hidden-secret" not in repr(created[0])
    assert "hidden-key" not in repr(created[0])


def test_default_composition_wraps_frozen_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[VstConfiguration] = []
    fake = AsyncReadOnlyFake()

    def factory(value: VstConfiguration) -> AsyncReadOnlyFake:
        created.append(value)
        return fake

    monkeypatch.setattr(command, "create_async_readiness_transport", factory)

    def credential_provider(prompt: str) -> str:
        return "key" if prompt.endswith("key: ") else "secret"

    assert (
        command.main(
            [],
            credential_provider=credential_provider,
            output=lambda _: None,
            clock_ms=lambda: NOW,
        )
        == 0
    )
    assert len(created) == 1
    concrete = create_async_readiness_transport(configuration())
    assert isinstance(concrete, BingXAsyncReadinessAdapter)
    assert isinstance(concrete._client, BingXHttpClient)
    assert concrete._client._base_urls == (
        "https://open-api-vst.bingx.com",
        "https://open-api-vst.bingx.pro",
    )


def test_adapter_exposes_only_approved_operations() -> None:
    public = {
        name for name in dir(BingXAsyncReadinessAdapter) if not name.startswith("_")
    }
    assert public == {
        "close",
        "fetch_balance",
        "fetch_positions",
        "fetch_server_time",
        "selected_host",
    }
    forbidden = {
        "submit_intent",
        "create_order",
        "cancel_order",
        "amend_order",
        "close_position",
        "place_order",
        "submit_order",
        "fetch_fills",
    }
    assert public.isdisjoint(forbidden)


@pytest.mark.asyncio
async def test_clock_drift_stops_before_account_reads_and_closes() -> None:
    fake = AsyncReadOnlyFake()
    fake.server_time = NOW + 5_000
    report = await check_vst_readiness(configuration(), fake, clock_ms=lambda: NOW)
    assert report.reason_codes == ("clock_drift_exceeded",)
    assert fake.calls == ["fetch_server_time", "close"]
    assert fake.closed


@pytest.mark.asyncio
async def test_midpoint_clock_sampling_excludes_full_round_trip_latency() -> None:
    fake = AsyncReadOnlyFake()
    fake.server_time = NOW + 500
    wall_times = iter((NOW, NOW + 1_000))
    monotonic_times = iter((1.0, 2.0))
    report = await check_vst_readiness(
        configuration(),
        fake,
        clock_ms=lambda: next(wall_times),
        monotonic=lambda: next(monotonic_times),
    )
    assert report.clock_drift_ms == 0
    assert report.round_trip_ms == 1_000
    assert report.status is ReadinessStatus.READY


@pytest.mark.asyncio
async def test_slow_first_sample_then_reliable_sample_succeeds() -> None:
    fake = AsyncReadOnlyFake()
    fake.server_times = [11_500, 20_250]
    fake.selected_hosts = [
        "https://open-api-vst.bingx.com",
        "https://open-api-vst.bingx.pro",
    ]
    wall_times = iter((10_000, 13_000, 20_000, 20_500))
    monotonic_times = iter((1.0, 4.0, 5.0, 5.5))
    report = await check_vst_readiness(
        configuration(),
        fake,
        clock_ms=lambda: next(wall_times),
        monotonic=lambda: next(monotonic_times),
    )
    assert report.status is ReadinessStatus.READY
    assert report.clock_drift_ms == 0
    assert report.round_trip_ms == 500
    assert report.selected_host == "https://open-api-vst.bingx.pro"
    assert fake.calls == [
        "fetch_server_time",
        "fetch_server_time",
        "fetch_balance",
        "fetch_positions",
        "close",
    ]


@pytest.mark.asyncio
async def test_lowest_rtt_valid_sample_and_its_host_are_selected() -> None:
    fake = AsyncReadOnlyFake()
    fake.server_times = [10_500, 20_300, 30_400]
    fake.selected_hosts = [
        "https://open-api-vst.bingx.com",
        "https://open-api-vst.bingx.pro",
        "https://open-api-vst.bingx.com",
    ]
    wall_times = iter((10_000, 11_000, 20_000, 20_600, 30_000, 30_800))
    monotonic_times = iter((1.0, 2.0, 3.0, 3.6, 5.0, 5.8))
    report = await check_vst_readiness(
        configuration(),
        fake,
        clock_ms=lambda: next(wall_times),
        monotonic=lambda: next(monotonic_times),
    )
    assert report.round_trip_ms == 600
    assert report.clock_drift_ms == 0
    assert report.server_timestamp_ms == 20_300
    assert report.local_timestamp_ms == 20_300
    assert report.selected_host == "https://open-api-vst.bingx.pro"
    assert fake.calls.count("fetch_server_time") == 3
    assert fake.calls.count("fetch_balance") == 1
    assert fake.calls.count("fetch_positions") == 1


@pytest.mark.asyncio
async def test_each_sample_uses_its_own_midpoint_for_drift() -> None:
    fake = AsyncReadOnlyFake()
    fake.server_times = [11_600, 20_400, 30_450]
    wall_times = iter((10_000, 13_000, 20_000, 20_800, 30_000, 30_900))
    monotonic_times = iter((1.0, 4.0, 5.0, 5.8, 7.0, 7.9))
    report = await check_vst_readiness(
        configuration(),
        fake,
        clock_ms=lambda: next(wall_times),
        monotonic=lambda: next(monotonic_times),
    )
    assert report.round_trip_ms == 800
    assert report.local_timestamp_ms == 20_400
    assert report.server_timestamp_ms == 20_400
    assert report.clock_drift_ms == 0


@pytest.mark.asyncio
async def test_immediately_reliable_sample_stops_sampling_early() -> None:
    fake = AsyncReadOnlyFake()
    fake.server_times = [10_050, 99_999, 99_999]
    wall_times = iter((10_000, 10_100))
    monotonic_times = iter((1.0, 1.1))
    report = await check_vst_readiness(
        configuration(),
        fake,
        clock_ms=lambda: next(wall_times),
        monotonic=lambda: next(monotonic_times),
    )
    assert report.status is ReadinessStatus.READY
    assert report.round_trip_ms == 100
    assert fake.calls.count("fetch_server_time") == 1


@pytest.mark.asyncio
async def test_three_unreliable_samples_fail_with_lowest_sanitized_rtt() -> None:
    fake = AsyncReadOnlyFake()
    fake.server_times = [11_500, 21_250, 31_400]
    fake.selected_hosts = [
        "https://open-api-vst.bingx.com",
        "https://open-api-vst.bingx.pro",
        "https://open-api-vst.bingx.com",
    ]
    wall_times = iter((10_000, 13_000, 20_000, 22_500, 30_000, 32_800))
    monotonic_times = iter((1.0, 4.0, 5.0, 7.5, 9.0, 11.8))
    report = await check_vst_readiness(
        configuration(),
        fake,
        clock_ms=lambda: next(wall_times),
        monotonic=lambda: next(monotonic_times),
    )
    assert report.reason_codes == ("clock_sample_unreliable",)
    assert report.round_trip_ms == 2_500
    assert report.selected_host == "https://open-api-vst.bingx.pro"
    assert fake.calls == ["fetch_server_time"] * 3 + ["close"]
    assert not report.authenticated_account_read


@pytest.mark.asyncio
async def test_connection_refusal_is_not_tls_failure() -> None:
    fake = AsyncReadOnlyFake()
    fake.failure = network_error(ConnectionRefusedError(10061, "private"))
    report = await check_vst_readiness(configuration(), fake, clock_ms=lambda: NOW)
    assert report.reason_codes == ("connection_refused",)
    assert "private" not in report.to_json()
    assert "tls_failure" not in report.reason_codes


@pytest.mark.asyncio
async def test_http_403_is_sanitized_and_not_tls_failure() -> None:
    fake = AsyncReadOnlyFake()
    fake.failure = ExchangeError(
        message="private response",
        exchange="bingx",
        error_code=403,
    )
    report = await check_vst_readiness(configuration(), fake, clock_ms=lambda: NOW)
    assert report.reason_codes == ("http_status_failure",)
    assert "private response" not in report.to_json()
    assert "tls_failure" not in report.reason_codes


@pytest.mark.asyncio
async def test_invalid_server_time_schema_stops_before_authenticated_reads() -> None:
    fake = AsyncReadOnlyFake()
    fake.server_time = {"serverTime": "invalid"}
    report = await check_vst_readiness(configuration(), fake, clock_ms=lambda: NOW)
    assert report.reason_codes == ("invalid_server_time_schema",)
    assert fake.calls == ["fetch_server_time"] * 3 + ["close"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        (
            AuthenticationError(message="private", exchange="bingx"),
            "authentication_rejected",
        ),
        (TimeoutError("private"), "connect_timeout"),
    ],
)
async def test_sanitized_failures_close(failure: Exception, reason: str) -> None:
    fake = AsyncReadOnlyFake()
    fake.failure = failure
    report = await check_vst_readiness(configuration(), fake, clock_ms=lambda: NOW)
    assert report.status is ReadinessStatus.FAILED
    assert reason in report.reason_codes
    assert "private" not in report.to_json()
    assert fake.closed


def network_error(cause: BaseException) -> NetworkError:
    try:
        raise cause
    except BaseException as error:
        try:
            raise NetworkError(message="sanitized", exchange="bingx") from error
        except NetworkError as wrapped:
            return wrapped


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        (
            network_error(__import__("socket").gaierror(11001, "private-host")),
            "dns_failure",
        ),
        (
            network_error(__import__("ssl").SSLError("private-tls")),
            "tls_handshake_failure",
        ),
        (
            network_error(__import__("httpx").ConnectTimeout("private-connect")),
            "connect_timeout",
        ),
        (
            network_error(__import__("httpx").ReadTimeout("private-read")),
            "read_timeout",
        ),
        (
            ExchangeError(
                message="private-http",
                exchange="bingx",
                error_code=503,
            ),
            "http_status_failure",
        ),
        (
            AuthenticationError(
                message="private-signature",
                exchange="bingx",
                error_code=100004,
            ),
            "signature_rejected",
        ),
    ],
)
async def test_stable_failure_mapping(failure: Exception, reason: str) -> None:
    fake = AsyncReadOnlyFake()
    fake.failure = failure
    report = await check_vst_readiness(configuration(), fake, clock_ms=lambda: NOW)
    assert report.reason_codes == (reason,)
    assert "private" not in report.to_json()
    assert fake.calls == ["fetch_server_time"] * 3 + ["close"]


@pytest.mark.asyncio
async def test_obsolete_server_time_path_is_invalid_endpoint_not_tls_failure() -> None:
    fake = AsyncReadOnlyFake()
    fake.failure = ExchangeError(
        message="BingX error [100404]: this api is not exist",
        exchange="bingx",
        error_code=100404,
        operation="GET /openApi/swap/v1/server/time",
    )

    report = await check_vst_readiness(configuration(), fake, clock_ms=lambda: NOW)

    assert report.reason_codes == ("invalid_endpoint",)
    assert report.recommended_action == "verify_bingx_vst_api_compatibility"
    assert "this api is not exist" not in report.to_json()
    assert "tls_failure" not in report.reason_codes
    assert fake.calls == ["fetch_server_time"] * 3 + ["close"]


@pytest.mark.asyncio
async def test_malformed_balance_and_positions_fail_closed() -> None:
    fake = AsyncReadOnlyFake()
    fake.balances = ({"balance": 100},)
    report = await check_vst_readiness(configuration(), fake, clock_ms=lambda: NOW)
    assert report.reason_codes == ("invalid_balance_schema",)
    assert fake.closed

    fake2 = AsyncReadOnlyFake()
    fake2.positions = ({"symbol": "BTC-USDT"},)
    report2 = await check_vst_readiness(configuration(), fake2, clock_ms=lambda: NOW)
    assert report2.reason_codes == ("invalid_positions_schema",)
    assert fake2.closed


def test_failed_command_is_sanitized_nonzero() -> None:
    fake = AsyncReadOnlyFake()
    fake.failure = AuthenticationError(message="raw-secret", exchange="bingx")
    output: list[str] = []

    def credential_provider(prompt: str) -> str:
        return "key" if prompt.endswith("key: ") else "secret"

    code = command.main(
        [],
        credential_provider=credential_provider,
        transport_provider=lambda _: fake,
        output=output.append,
        clock_ms=lambda: NOW,
    )
    assert code == 1
    assert "raw-secret" not in "".join(output)
    assert fake.closed


def test_asyncio_run_only_occurs_in_manual_main_and_import_is_safe() -> None:
    module = importlib.import_module("scripts.bingx_vst_readiness")
    assert callable(module.main)
    root = Path(__file__).parents[3]
    production = (
        root / "src" / "vst_runtime" / "readiness.py",
        root / "scripts" / "bingx_vst_readiness.py",
    )
    occurrences: list[tuple[str, str]] = []
    for path in production:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "asyncio"
                and node.func.attr == "run"
            ):
                parent = next(
                    item
                    for item in ast.walk(tree)
                    if isinstance(item, ast.FunctionDef)
                    and node in tuple(ast.walk(item))
                )
                occurrences.append((path.name, parent.name))
    assert occurrences == [("bingx_vst_readiness.py", "main")]
