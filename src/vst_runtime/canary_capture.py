"""Attested read-only acquisition for canonical BingX VST canary inputs."""

from __future__ import annotations

import hashlib
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from math import isfinite
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from src.exchange.bingx_client import BingXHttpClient
from src.exchange.models import BingXKline, BingXPosition
from src.execution_intent.models import decimal_text
from src.risk.kill_switch import KillSwitch

from .demo_order import (
    DEFAULT_DEMO_CANARY_POLICY,
    DemoCanaryError,
    DemoContractConstraints,
    DemoLeverageSnapshot,
    DemoTopOfBook,
)
from .demo_transport import BingXAsyncDemoOrderAdapter
from .intent_preparation import (
    ACCOUNT_SCHEMA_VERSION,
    ARTIFACT_DIRECTORY_NAME,
    CONSTRAINTS_SCHEMA_VERSION,
    MARKET_SCHEMA_VERSION,
    POLICY_SCHEMA_VERSION,
)
from .models import VST_BASE_URLS, RemoteOrder, VstConfiguration, canonical
from .readiness import (
    AsyncReadinessTransport,
    ReadinessStatus,
    VstReadinessReport,
    check_vst_readiness,
)

Clock = Callable[[], int]
ReadinessProvider = Callable[[VstConfiguration], AsyncReadinessTransport]

CAPTURE_MANIFEST_SCHEMA_VERSION = "bingx-vst-canary-capture-manifest-v1"
CAPTURE_POLICY_VERSION = "bingx-vst-canary-input-policy-v1"
CAPTURE_DIRECTORY_NAME = "canary-inputs"
CAPTURE_STATUS = "CAPTURED"
CANARY_SYMBOL = "BTC-USDT"
CANARY_TIMEFRAME = "3m"
CANARY_CANDLE_INTERVAL_MS = 180_000
_CANDLE_LIMIT = 100
_MINIMUM_COMPLETED_CANDLES = 3
_INCOME_LIMIT = 1_000
_INPUT_FILENAMES = (
    "account-input.json",
    "constraints-input.json",
    "market-input.json",
    "policy-input.json",
)
_MANIFEST_FILENAME = "manifest.json"
_SETTLEMENT_ASSETS = ("VST", "USDT")
_NON_TRADING_INCOME_TYPES = frozenset({"TRANSFER", "TRIAL_FUND"})
_KNOWN_INCOME_TYPES = frozenset(
    {
        "ADL",
        "FUNDING_FEE",
        "GTD_PRICE",
        "INSURANCE_CLEAR",
        "REALIZED_PNL",
        "SYSTEM_DEDUCTION",
        "TRADING_FEE",
        *_NON_TRADING_INCOME_TYPES,
    }
)


class CanaryCaptureError(Exception):
    """Sanitized stable blocker for the manual acquisition boundary."""

    def __init__(self, reason_code: str, *, selected_host: str | None = None) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.selected_host = selected_host


@dataclass(frozen=True, slots=True)
class CapturedBalance:
    """Strict account fields required by the canonical risk snapshot."""

    asset: str
    wallet_balance: Decimal
    equity: Decimal
    available_balance: Decimal
    used_margin: Decimal

    def __post_init__(self) -> None:
        asset = _required_text(self.asset, "incomplete_account_response").upper()
        object.__setattr__(self, "asset", asset)
        for name in (
            "wallet_balance",
            "equity",
            "available_balance",
            "used_margin",
        ):
            value = _non_negative_decimal(
                getattr(self, name), "incomplete_account_response"
            )
            object.__setattr__(self, name, value)
        if self.equity <= 0 or self.wallet_balance <= 0:
            raise CanaryCaptureError("incomplete_account_response")
        if self.available_balance > self.equity:
            raise CanaryCaptureError("incomplete_account_response")


@dataclass(frozen=True, slots=True)
class CapturedIncome:
    """One strict read-only fund-flow fact used for conservative daily risk."""

    income_type: str
    income: Decimal
    asset: str
    timestamp_ms: int
    transaction_id: str

    def __post_init__(self) -> None:
        income_type = _required_text(
            self.income_type, "invalid_income_schema"
        ).upper()
        if income_type not in _KNOWN_INCOME_TYPES:
            raise CanaryCaptureError("invalid_income_schema")
        object.__setattr__(self, "income_type", income_type)
        object.__setattr__(
            self,
            "income",
            _decimal(self.income, "invalid_income_schema"),
        )
        object.__setattr__(
            self,
            "asset",
            _required_text(self.asset, "invalid_income_schema").upper(),
        )
        if (
            isinstance(self.timestamp_ms, bool)
            or not isinstance(self.timestamp_ms, int)
            or self.timestamp_ms < 0
        ):
            raise CanaryCaptureError("invalid_income_schema")
        object.__setattr__(
            self,
            "transaction_id",
            _required_text(self.transaction_id, "invalid_income_schema"),
        )


@runtime_checkable
class AsyncCanaryCaptureTransport(Protocol):
    """Complete and exclusively read-only network surface for capture."""

    async def fetch_candles(
        self, symbol: str, timeframe: str, limit: int
    ) -> Sequence[BingXKline]: ...

    async def fetch_orderbook(self, symbol: str) -> DemoTopOfBook: ...

    async def fetch_account_balances(self) -> Sequence[CapturedBalance]: ...

    async def fetch_positions(self) -> Sequence[BingXPosition]: ...

    async def fetch_constraints(self, symbol: str) -> DemoContractConstraints: ...

    async def fetch_leverage(self, symbol: str) -> DemoLeverageSnapshot: ...

    async def fetch_position_mode(self) -> str: ...

    async def fetch_open_orders(self, symbol: str) -> Sequence[RemoteOrder]: ...

    async def fetch_income(
        self, *, start_time_ms: int, end_time_ms: int, limit: int
    ) -> Sequence[CapturedIncome]: ...

    async def close(self) -> None: ...

    @property
    def selected_host(self) -> str: ...


CaptureProvider = Callable[
    [VstConfiguration, str], AsyncCanaryCaptureTransport
]


class BingXAsyncCanaryCaptureAdapter:
    """Read-only facade over the existing frozen BingX client and mappings."""

    __slots__ = ("__client", "__demo_reads")

    def __init__(self, client: BingXHttpClient) -> None:
        if not isinstance(client, BingXHttpClient):
            raise TypeError("client must be a BingXHttpClient")
        self.__client = client
        self.__demo_reads = BingXAsyncDemoOrderAdapter(client)

    @property
    def selected_host(self) -> str:
        return self.__client.last_attempted_base_url

    async def fetch_candles(
        self, symbol: str, timeframe: str, limit: int
    ) -> Sequence[BingXKline]:
        return tuple(
            await self.__client.get_klines(
                symbol,
                interval=timeframe,
                limit=limit,
            )
        )

    async def fetch_orderbook(self, symbol: str) -> DemoTopOfBook:
        return await self.__demo_reads.fetch_orderbook(symbol)

    async def fetch_account_balances(self) -> Sequence[CapturedBalance]:
        response = await self.__client.request(
            "GET",
            "/openApi/swap/v3/user/balance",
            signed=True,
        )
        return _parse_captured_balances(response)

    async def fetch_positions(self) -> Sequence[BingXPosition]:
        return tuple(await self.__client.get_positions())

    async def fetch_constraints(self, symbol: str) -> DemoContractConstraints:
        contracts = await self.__client.get_symbols()
        return _parse_contract_constraints(contracts, symbol)

    async def fetch_leverage(self, symbol: str) -> DemoLeverageSnapshot:
        return await self.__demo_reads.fetch_leverage(symbol)

    async def fetch_position_mode(self) -> str:
        return await self.__demo_reads.fetch_position_mode()

    async def fetch_open_orders(self, symbol: str) -> Sequence[RemoteOrder]:
        return tuple(await self.__demo_reads.fetch_open_orders(symbol))

    async def fetch_income(
        self, *, start_time_ms: int, end_time_ms: int, limit: int
    ) -> Sequence[CapturedIncome]:
        response = await self.__client.request(
            "GET",
            "/openApi/swap/v2/user/income",
            params={
                "startTime": start_time_ms,
                "endTime": end_time_ms,
                "limit": limit,
            },
            signed=True,
        )
        return _parse_income(response)

    async def close(self) -> None:
        await self.__client.close()


def create_async_canary_capture_transport(
    configuration: VstConfiguration,
    selected_host: str,
) -> AsyncCanaryCaptureTransport:
    """Create the frozen client pinned to readiness's actual VST host."""

    host = _vst_host(selected_host)
    if configuration.base_url not in VST_BASE_URLS:
        raise CanaryCaptureError("host_not_vst")
    client = BingXHttpClient(
        api_key=configuration.api_key,
        api_secret=configuration.api_secret,
        demo_mode=True,
        base_url=host,
        recv_window=configuration.recv_window_ms,
        timeout=configuration.timeout_seconds,
    )
    return BingXAsyncCanaryCaptureAdapter(client)


@dataclass(frozen=True, slots=True)
class CanaryCaptureReport:
    """Canonical secret-free result and exact operator handoff commands."""

    status: str
    capture_id: str | None
    artifact_directory: str | None
    selected_host: str | None
    created_at: str | None
    expires_at: str | None
    input_digests: tuple[tuple[str, str], ...]
    preparation_command: str | None
    dry_run_command: str | None
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        reasons = tuple(sorted(set(self.reason_codes)))
        if not reasons:
            raise ValueError("capture report requires a reason")
        object.__setattr__(self, "reason_codes", reasons)
        normalized_digests = tuple(sorted(self.input_digests))
        if len(dict(normalized_digests)) != len(normalized_digests):
            raise ValueError("capture report digests are invalid")
        object.__setattr__(self, "input_digests", normalized_digests)
        if self.status == CAPTURE_STATUS:
            required = (
                self.capture_id,
                self.artifact_directory,
                self.selected_host,
                self.created_at,
                self.expires_at,
                self.preparation_command,
                self.dry_run_command,
            )
            if any(value is None for value in required):
                raise ValueError("captured report is incomplete")

    @classmethod
    def blocked(
        cls,
        reason_code: str,
        *,
        selected_host: str | None = None,
    ) -> CanaryCaptureReport:
        return cls(
            status="BLOCKED",
            capture_id=None,
            artifact_directory=None,
            selected_host=selected_host,
            created_at=None,
            expires_at=None,
            input_digests=(),
            preparation_command=None,
            dry_run_command=None,
            reason_codes=(reason_code,),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_directory": self.artifact_directory,
            "capture_id": self.capture_id,
            "created_at": self.created_at,
            "dry_run_command": self.dry_run_command,
            "expires_at": self.expires_at,
            "input_digests": dict(self.input_digests),
            "preparation_command": self.preparation_command,
            "reason_codes": list(self.reason_codes),
            "selected_host": self.selected_host,
            "status": self.status,
        }

    def to_json(self) -> str:
        return canonical(self.to_dict())


@dataclass(frozen=True, slots=True)
class _CapturedDocuments:
    files: tuple[tuple[str, str], ...]
    manifest: str
    capture_id: str
    selected_host: str
    created_at: str
    expires_at: str


async def capture_canary_inputs(
    configuration: VstConfiguration,
    *,
    readiness_provider: ReadinessProvider,
    capture_provider: CaptureProvider,
    local_kill_switch: KillSwitch | None,
    artifact_root: Path,
    clock_ms: Clock,
    monotonic: Callable[[], float] = time.monotonic,
) -> CanaryCaptureReport:
    """Run readiness, acquire all read-only facts, then write one bundle."""

    if not isinstance(configuration, VstConfiguration):
        raise CanaryCaptureError("invalid_configuration")
    if not callable(readiness_provider) or not callable(capture_provider):
        raise CanaryCaptureError("invalid_composition")
    if not isinstance(local_kill_switch, KillSwitch):
        raise CanaryCaptureError("risk_state_unavailable")
    if local_kill_switch.active:
        raise CanaryCaptureError("kill_switch_active")
    if not callable(clock_ms):
        raise CanaryCaptureError("invalid_clock")

    try:
        readiness_transport = readiness_provider(configuration)
        readiness = await check_vst_readiness(
            configuration,
            readiness_transport,
            clock_ms=clock_ms,
            monotonic=monotonic,
        )
    except CanaryCaptureError:
        raise
    except Exception:
        raise CanaryCaptureError("readiness_failed") from None
    if readiness.status is not ReadinessStatus.READY:
        raise CanaryCaptureError(_readiness_reason(readiness))

    capture_time_ms = _clock_value(clock_ms())
    day_start_ms = _utc_day_start_ms(capture_time_ms)
    transport: AsyncCanaryCaptureTransport | None = None
    documents: _CapturedDocuments | None = None
    acquisition_error: CanaryCaptureError | None = None
    try:
        transport = capture_provider(configuration, readiness.selected_host)
        candles = tuple(
            await transport.fetch_candles(
                CANARY_SYMBOL,
                CANARY_TIMEFRAME,
                _CANDLE_LIMIT,
            )
        )
        orderbook = await transport.fetch_orderbook(CANARY_SYMBOL)
        balances = tuple(await transport.fetch_account_balances())
        positions = tuple(await transport.fetch_positions())
        constraints = await transport.fetch_constraints(CANARY_SYMBOL)
        leverage = await transport.fetch_leverage(CANARY_SYMBOL)
        position_mode = await transport.fetch_position_mode()
        open_orders = tuple(await transport.fetch_open_orders(CANARY_SYMBOL))
        income = tuple(
            await transport.fetch_income(
                start_time_ms=day_start_ms,
                end_time_ms=capture_time_ms,
                limit=_INCOME_LIMIT,
            )
        )
        selected_host = _vst_host(transport.selected_host)
        validation_time_ms = _clock_value(clock_ms())
        if (
            validation_time_ms
            > capture_time_ms + DEFAULT_DEMO_CANARY_POLICY.intent_ttl_ms
        ):
            raise CanaryCaptureError("capture_stale")
        documents = _canonical_documents(
            readiness=readiness,
            selected_host=selected_host,
            capture_time_ms=capture_time_ms,
            validation_time_ms=validation_time_ms,
            candles=candles,
            orderbook=orderbook,
            balances=balances,
            positions=positions,
            constraints=constraints,
            leverage=leverage,
            position_mode=position_mode,
            open_orders=open_orders,
            income=income,
            income_start_ms=day_start_ms,
            local_kill_switch=local_kill_switch,
        )
    except CanaryCaptureError as error:
        acquisition_error = error
    except DemoCanaryError as error:
        acquisition_error = CanaryCaptureError(error.reason_code)
    except Exception:
        acquisition_error = CanaryCaptureError("capture_read_failed")
    finally:
        if transport is not None:
            try:
                await transport.close()
            except Exception:
                acquisition_error = CanaryCaptureError("transport_close_failed")

    if acquisition_error is not None:
        attempted_host = readiness.selected_host
        if transport is not None:
            try:
                attempted_host = _vst_host(transport.selected_host)
            except CanaryCaptureError:
                pass
        raise CanaryCaptureError(
            acquisition_error.reason_code,
            selected_host=attempted_host,
        ) from None
    if documents is None:
        raise CanaryCaptureError("capture_failed")
    relative_directory = _write_bundle(artifact_root, documents)
    digest_items = tuple(
        (name, hashlib.sha256(content.encode("utf-8")).hexdigest())
        for name, content in documents.files
    )
    digest_map = dict(digest_items)
    return CanaryCaptureReport(
        status=CAPTURE_STATUS,
        capture_id=documents.capture_id,
        artifact_directory=relative_directory,
        selected_host=documents.selected_host,
        created_at=documents.created_at,
        expires_at=documents.expires_at,
        input_digests=digest_items,
        preparation_command=_preparation_command(
            relative_directory,
            digest_map,
        ),
        dry_run_command=_dry_run_command(documents.selected_host),
        reason_codes=("capture_complete",),
    )


def _canonical_documents(
    *,
    readiness: VstReadinessReport,
    selected_host: str,
    capture_time_ms: int,
    validation_time_ms: int,
    candles: Sequence[BingXKline],
    orderbook: DemoTopOfBook,
    balances: Sequence[CapturedBalance],
    positions: Sequence[BingXPosition],
    constraints: DemoContractConstraints,
    leverage: DemoLeverageSnapshot,
    position_mode: str,
    open_orders: Sequence[RemoteOrder],
    income: Sequence[CapturedIncome],
    income_start_ms: int,
    local_kill_switch: KillSwitch,
) -> _CapturedDocuments:
    if (
        constraints.minimum_notional
        > DEFAULT_DEMO_CANARY_POLICY.maximum_notional
        or constraints.minimum_quantity * orderbook.best_ask
        > DEFAULT_DEMO_CANARY_POLICY.maximum_notional
    ):
        raise CanaryCaptureError("canary_contract_minimum_exceeds_cap")
    market_values, market_attestation = _market_values(
        candles,
        orderbook,
        capture_time_ms=capture_time_ms,
        validation_time_ms=validation_time_ms,
    )
    account_values, account_attestation = _account_values(
        balances,
        positions,
        open_orders,
        income,
        capture_time_ms=capture_time_ms,
        income_start_ms=income_start_ms,
        local_kill_switch=local_kill_switch,
    )
    constraints_values, constraints_attestation = _constraints_values(
        constraints,
        leverage,
        position_mode,
        capture_time_ms=capture_time_ms,
    )
    policy_values = _fixed_policy_values()
    values_by_name = {
        "account-input.json": account_values,
        "constraints-input.json": constraints_values,
        "market-input.json": market_values,
        "policy-input.json": policy_values,
    }
    serialized = tuple(
        (name, canonical(values_by_name[name])) for name in _INPUT_FILENAMES
    )
    file_digests = {
        name: hashlib.sha256(content.encode("utf-8")).hexdigest()
        for name, content in serialized
    }
    created_at = _timestamp(capture_time_ms)
    expires_at = _timestamp(
        capture_time_ms + DEFAULT_DEMO_CANARY_POLICY.intent_ttl_ms
    )
    capture_material = {
        "account_attestation_digest": account_attestation,
        "canary_policy": _canary_policy_attestation(),
        "canary_policy_id": _digest(_canary_policy_attestation()),
        "constraints_attestation_digest": constraints_attestation,
        "created_at": created_at,
        "expires_at": expires_at,
        "files": file_digests,
        "market_attestation_digest": market_attestation,
        "policy_input_digest": file_digests["policy-input.json"],
        "readiness_result_digest": readiness.digest,
        "risk_state_sources": {
            "kill_switch": "process-local-existing-service",
            "loss_history": "bingx-vst-income",
        },
        "selected_host": selected_host,
        "symbol": CANARY_SYMBOL,
    }
    capture_id = hashlib.sha256(canonical(capture_material).encode()).hexdigest()
    manifest_values = {
        **capture_material,
        "capture_id": capture_id,
        "schema_version": CAPTURE_MANIFEST_SCHEMA_VERSION,
    }
    return _CapturedDocuments(
        files=serialized,
        manifest=canonical(manifest_values),
        capture_id=capture_id,
        selected_host=selected_host,
        created_at=created_at,
        expires_at=expires_at,
    )


def _market_values(
    candles: Sequence[BingXKline],
    orderbook: DemoTopOfBook,
    *,
    capture_time_ms: int,
    validation_time_ms: int,
) -> tuple[dict[str, object], str]:
    if not isinstance(orderbook, DemoTopOfBook) or orderbook.symbol != CANARY_SYMBOL:
        raise CanaryCaptureError("invalid_orderbook_schema")
    if any(not isinstance(item, BingXKline) for item in candles):
        raise CanaryCaptureError("invalid_candle_schema")
    completed = tuple(
        sorted(
            (
                item
                for item in candles
                if _effective_candle_close_ms(item) <= capture_time_ms
            ),
            key=lambda item: item.open_time,
        )
    )
    if len(completed) < _MINIMUM_COMPLETED_CANDLES:
        raise CanaryCaptureError("insufficient_completed_candles")
    open_times = tuple(_datetime_ms(item.open_time) for item in completed)
    if len(set(open_times)) != len(open_times):
        raise CanaryCaptureError("duplicate_candles")
    for index, item in enumerate(completed):
        open_ms = open_times[index]
        close_ms = _effective_candle_close_ms(item)
        if close_ms < open_ms or close_ms >= open_ms + CANARY_CANDLE_INTERVAL_MS:
            raise CanaryCaptureError("incomplete_candle")
        if index and open_ms - open_times[index - 1] != CANARY_CANDLE_INTERVAL_MS:
            raise CanaryCaptureError("candle_sequence_invalid")
    latest_open_ms = open_times[-1]
    policy = DEFAULT_DEMO_CANARY_POLICY
    if latest_open_ms > validation_time_ms + policy.future_tolerance_ms:
        raise CanaryCaptureError("candle_timestamp_invalid")
    if validation_time_ms > latest_open_ms + policy.intent_ttl_ms:
        raise CanaryCaptureError("stale_candles")
    rows = [
        [
            _timestamp(_datetime_ms(item.open_time)),
            _json_number(item.open),
            _json_number(item.high),
            _json_number(item.low),
            _json_number(item.close),
            _json_number(item.volume),
        ]
        for item in completed
    ]
    values: dict[str, object] = {
        "events": [
            {
                "kind": "candles",
                "payload": {
                    "candles": rows,
                    "symbol": CANARY_SYMBOL,
                    "timeframe": CANARY_TIMEFRAME,
                },
                "sequence": 1,
            }
        ],
        "exchange": "bingx",
        "schema_version": MARKET_SCHEMA_VERSION,
        "symbol": CANARY_SYMBOL,
        "timeframe": CANARY_TIMEFRAME,
    }
    attestation = _digest(
        {
            "best_ask": orderbook.best_ask,
            "best_bid": orderbook.best_bid,
            "candle_count": len(completed),
            "latest_completed_open_time": _timestamp(latest_open_ms),
            "orderbook_update_id": orderbook.update_id,
            "symbol": orderbook.symbol,
        }
    )
    return values, attestation


def _effective_candle_close_ms(candle: BingXKline) -> int:
    """Resolve only the proven three-minute mapping ambiguity at capture."""

    open_ms = _datetime_ms(candle.open_time)
    close_ms = _datetime_ms(candle.close_time)
    if close_ms == open_ms:
        # The frozen client maps BingX's mapping-form ``time`` field to both
        # timestamps when no explicit closeTime is present.  For this fixed
        # three-minute canary boundary, the candle closes at the final millisecond.
        return open_ms + CANARY_CANDLE_INTERVAL_MS - 1
    return close_ms


def _account_values(
    balances: Sequence[CapturedBalance],
    positions: Sequence[BingXPosition],
    open_orders: Sequence[RemoteOrder],
    income: Sequence[CapturedIncome],
    *,
    capture_time_ms: int,
    income_start_ms: int,
    local_kill_switch: KillSwitch,
) -> tuple[dict[str, object], str]:
    if not balances or any(not isinstance(item, CapturedBalance) for item in balances):
        raise CanaryCaptureError("incomplete_account_response")
    settlement: CapturedBalance | None = None
    for asset in _SETTLEMENT_ASSETS:
        matches = tuple(item for item in balances if item.asset == asset)
        if len(matches) > 1:
            raise CanaryCaptureError("incomplete_account_response")
        if matches:
            settlement = matches[0]
            break
    if settlement is None:
        raise CanaryCaptureError("settlement_balance_missing")
    if any(not isinstance(item, BingXPosition) for item in positions):
        raise CanaryCaptureError("invalid_positions_schema")
    active_positions = tuple(item for item in positions if item.position_amount != 0)
    if any(item.symbol.upper() == CANARY_SYMBOL for item in active_positions):
        raise CanaryCaptureError("existing_symbol_position")
    if active_positions:
        raise CanaryCaptureError("portfolio_risk_unavailable")
    if any(not isinstance(item, RemoteOrder) for item in open_orders):
        raise CanaryCaptureError("invalid_open_orders_schema")
    if open_orders:
        raise CanaryCaptureError("existing_open_entry_order")
    if settlement.used_margin != 0:
        raise CanaryCaptureError("account_risk_facts_unavailable")
    daily_loss, consecutive_losses, income_digest = _risk_from_income(
        income,
        settlement,
        start_time_ms=income_start_ms,
        end_time_ms=capture_time_ms,
    )
    if not isinstance(local_kill_switch, KillSwitch):
        raise CanaryCaptureError("risk_state_unavailable")
    kill_switch_state = local_kill_switch.state
    if kill_switch_state.active:
        raise CanaryCaptureError("kill_switch_active")
    values: dict[str, object] = {
        "available_balance": decimal_text(settlement.available_balance),
        "current_exposure": "0",
        "equity": decimal_text(settlement.equity),
        "observed_at": _timestamp(capture_time_ms),
        "open_position_quantity": "0",
        "portfolio": {
            "balance": decimal_text(settlement.wallet_balance),
            "daily_loss": decimal_text(daily_loss),
            "equity": decimal_text(settlement.equity),
            "open_positions": 0,
            "total_risk": "0",
            "used_margin": "0",
        },
        "risk_state": {
            "circuit_breaker_consecutive_losses": consecutive_losses,
            "kill_switch_active": kill_switch_state.active,
        },
        "schema_version": ACCOUNT_SCHEMA_VERSION,
    }
    attestation = _digest(
        {
            "asset": settlement.asset,
            "available_balance": settlement.available_balance,
            "equity": settlement.equity,
            "income_digest": income_digest,
            "kill_switch_active": kill_switch_state.active,
            "kill_switch_source": "process-local-existing-service",
            "open_order_count": len(open_orders),
            "position_count": len(active_positions),
            "used_margin": settlement.used_margin,
            "wallet_balance": settlement.wallet_balance,
        }
    )
    return values, attestation


def _risk_from_income(
    income: Sequence[CapturedIncome],
    balance: CapturedBalance,
    *,
    start_time_ms: int,
    end_time_ms: int,
) -> tuple[Decimal, int, str]:
    if len(income) >= _INCOME_LIMIT:
        raise CanaryCaptureError("risk_history_incomplete")
    if any(not isinstance(item, CapturedIncome) for item in income):
        raise CanaryCaptureError("invalid_income_schema")
    identities: set[tuple[str, int, str]] = set()
    selected: list[CapturedIncome] = []
    for item in income:
        if item.asset != balance.asset:
            continue
        if not start_time_ms <= item.timestamp_ms <= end_time_ms:
            raise CanaryCaptureError("invalid_income_schema")
        identity = (item.transaction_id, item.timestamp_ms, item.income_type)
        if identity in identities:
            raise CanaryCaptureError("duplicate_income_records")
        identities.add(identity)
        selected.append(item)
    selected.sort(
        key=lambda item: (item.timestamp_ms, item.transaction_id),
        reverse=True,
    )
    gross_loss = sum(
        (
            -item.income
            for item in selected
            if item.income < 0
            and item.income_type not in _NON_TRADING_INCOME_TYPES
        ),
        Decimal(0),
    )
    daily_loss = gross_loss / balance.equity
    consecutive_losses = 0
    realized = tuple(
        item for item in selected if item.income_type == "REALIZED_PNL"
    )
    for item in realized:
        if item.income >= 0:
            break
        consecutive_losses += 1
    income_digest = _digest(
        {
            "end_time_ms": end_time_ms,
            "records": [
                {
                    "asset": item.asset,
                    "income": item.income,
                    "income_type": item.income_type,
                    "timestamp_ms": item.timestamp_ms,
                    "transaction_id": item.transaction_id,
                }
                for item in selected
            ],
            "start_time_ms": start_time_ms,
        }
    )
    return daily_loss.normalize(), consecutive_losses, income_digest


def _constraints_values(
    constraints: DemoContractConstraints,
    leverage: DemoLeverageSnapshot,
    position_mode: str,
    *,
    capture_time_ms: int,
) -> tuple[dict[str, object], str]:
    if (
        not isinstance(constraints, DemoContractConstraints)
        or constraints.symbol != CANARY_SYMBOL
        or not constraints.trading_enabled
    ):
        raise CanaryCaptureError("invalid_constraints_schema")
    if (
        not isinstance(leverage, DemoLeverageSnapshot)
        or leverage.symbol != CANARY_SYMBOL
    ):
        raise CanaryCaptureError("invalid_leverage_schema")
    if (
        leverage.long_leverage > DEFAULT_DEMO_CANARY_POLICY.maximum_leverage
        or leverage.short_leverage > DEFAULT_DEMO_CANARY_POLICY.maximum_leverage
        or leverage.long_leverage > constraints.maximum_long_leverage
        or leverage.short_leverage > constraints.maximum_short_leverage
    ):
        raise CanaryCaptureError("demo_leverage_cap_exceeded")
    if position_mode not in {"HEDGE", "ONE_WAY"}:
        raise CanaryCaptureError("invalid_position_mode_schema")
    values: dict[str, object] = {
        "exchange": "bingx",
        "maximum_quantity": None,
        "minimum_notional": decimal_text(constraints.minimum_notional),
        "minimum_quantity": decimal_text(constraints.minimum_quantity),
        "observed_at": _timestamp(capture_time_ms),
        "price_tick": decimal_text(constraints.price_tick),
        "quantity_step": decimal_text(constraints.quantity_step),
        "schema_version": CONSTRAINTS_SCHEMA_VERSION,
        "symbol": CANARY_SYMBOL,
    }
    attestation = _digest(
        {
            "constraints_snapshot_id": constraints.snapshot_id,
            "leverage_source": "bingx-authenticated-account",
            "long_leverage": leverage.long_leverage,
            "maximum_leverage_policy": DEFAULT_DEMO_CANARY_POLICY.maximum_leverage,
            "maximum_leverage_source": "fixed-canary-policy",
            "position_mode": position_mode,
            "short_leverage": leverage.short_leverage,
            "symbol": CANARY_SYMBOL,
        }
    )
    return values, attestation


def _fixed_policy_values() -> dict[str, object]:
    return {
        "execution": {
            "leverage": "2",
            "maximum_exposure_ratio": "0.8",
            "risk_percent": "0.1",
        },
        "risk_limits": {
            "circuit_breaker_cooldown_minutes": 60,
            "max_consecutive_losses": 3,
            "max_daily_loss": "0.1",
            "max_drawdown": "0.2",
            "max_leverage": "2",
            "max_margin_usage": "0.8",
            "max_portfolio_risk": "0.1",
            "max_position_size": "0.1",
            "max_positions": 1,
        },
        "schema_version": POLICY_SCHEMA_VERSION,
    }


def _canary_policy_attestation() -> dict[str, object]:
    return {
        "environment": "VST",
        "existing_same_symbol_position_allowed": False,
        "live_supported": False,
        "maximum_leverage": DEFAULT_DEMO_CANARY_POLICY.maximum_leverage,
        "maximum_quote_notional": DEFAULT_DEMO_CANARY_POLICY.maximum_notional,
        "no_pyramiding": True,
        "order_type": "LIMIT",
        "protected_order_required": True,
        "symbol": CANARY_SYMBOL,
        "ttl_ms": DEFAULT_DEMO_CANARY_POLICY.intent_ttl_ms,
        "version": CAPTURE_POLICY_VERSION,
    }


def _parse_captured_balances(
    response: Mapping[str, Any],
) -> tuple[CapturedBalance, ...]:
    data = response.get("data")
    if isinstance(data, Mapping):
        nested = data.get("balance", data)
        items = (nested,) if isinstance(nested, Mapping) else nested
    else:
        items = data
    if not isinstance(items, Sequence) or isinstance(
        items, (str, bytes, bytearray)
    ):
        raise CanaryCaptureError("incomplete_account_response")
    result: list[CapturedBalance] = []
    for item in items:
        if not isinstance(item, Mapping):
            raise CanaryCaptureError("incomplete_account_response")
        required = ("asset", "balance", "equity", "availableMargin", "usedMargin")
        if any(name not in item for name in required):
            raise CanaryCaptureError("incomplete_account_response")
        result.append(
            CapturedBalance(
                asset=item["asset"],
                wallet_balance=_decimal(
                    item["balance"], "incomplete_account_response"
                ),
                equity=_decimal(item["equity"], "incomplete_account_response"),
                available_balance=_decimal(
                    item["availableMargin"], "incomplete_account_response"
                ),
                used_margin=_decimal(
                    item["usedMargin"], "incomplete_account_response"
                ),
            )
        )
    return tuple(result)


def _parse_income(response: Mapping[str, Any]) -> tuple[CapturedIncome, ...]:
    if "data" not in response:
        raise CanaryCaptureError("invalid_income_schema")
    data = response["data"]
    if data is None:
        raw_code = response.get("code", 0)
        try:
            code = int(raw_code)
        except (TypeError, ValueError):
            code = -1
        if code == 0 and response.get("success", True) is not False:
            return ()
        raise CanaryCaptureError("invalid_income_schema")
    if isinstance(data, Mapping):
        data = data.get("income", data.get("records"))
    if not isinstance(data, Sequence) or isinstance(data, (str, bytes, bytearray)):
        raise CanaryCaptureError("invalid_income_schema")
    result: list[CapturedIncome] = []
    for item in data:
        if not isinstance(item, Mapping):
            raise CanaryCaptureError("invalid_income_schema")
        transaction_id = item.get("tranId", item.get("tradeId"))
        required = ("incomeType", "income", "asset", "time")
        if any(name not in item for name in required) or transaction_id is None:
            raise CanaryCaptureError("invalid_income_schema")
        result.append(
            CapturedIncome(
                income_type=item["incomeType"],
                income=_decimal(item["income"], "invalid_income_schema"),
                asset=item["asset"],
                timestamp_ms=_integer(item["time"], "invalid_income_schema"),
                transaction_id=str(transaction_id),
            )
        )
    return tuple(result)


def _parse_contract_constraints(
    contracts: Sequence[Mapping[str, Any]],
    symbol: str,
) -> DemoContractConstraints:
    if symbol != CANARY_SYMBOL or not isinstance(contracts, Sequence):
        raise CanaryCaptureError("invalid_constraints_schema")
    matches = tuple(item for item in contracts if item.get("symbol") == symbol)
    if not matches:
        raise CanaryCaptureError("contract_not_found")
    if len(matches) != 1:
        raise CanaryCaptureError("invalid_constraints_schema")
    item = matches[0]
    required = (
        "apiStateOpen",
        "pricePrecision",
        "quantityPrecision",
        "status",
        "symbol",
        "tradeMinQuantity",
        "tradeMinUSDT",
    )
    if any(name not in item for name in required):
        raise CanaryCaptureError("invalid_constraints_schema")
    if (
        isinstance(item["status"], bool)
        or not isinstance(item["status"], int)
        or item["status"] != 1
    ):
        raise CanaryCaptureError("contract_inactive")
    if not _api_state(item["apiStateOpen"]):
        raise CanaryCaptureError("contract_open_disabled")
    quantity_precision = _constraint_precision(item["quantityPrecision"])
    price_precision = _constraint_precision(item["pricePrecision"])
    minimum_quantity = _positive_constraint_decimal(item["tradeMinQuantity"])
    minimum_notional = _positive_constraint_decimal(item["tradeMinUSDT"])
    try:
        return DemoContractConstraints(
            symbol=symbol,
            price_tick=Decimal(1).scaleb(-price_precision),
            quantity_step=Decimal(1).scaleb(-quantity_precision),
            minimum_quantity=minimum_quantity,
            minimum_notional=minimum_notional,
            maximum_long_leverage=DEFAULT_DEMO_CANARY_POLICY.maximum_leverage,
            maximum_short_leverage=DEFAULT_DEMO_CANARY_POLICY.maximum_leverage,
            trading_enabled=True,
        )
    except (TypeError, ValueError):
        raise CanaryCaptureError("invalid_constraints_schema") from None


def _constraint_precision(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CanaryCaptureError("invalid_constraints_schema")
    if value < 0:
        raise CanaryCaptureError("invalid_constraints_schema")
    return value


def _positive_constraint_decimal(value: object) -> Decimal:
    result = _decimal(value, "invalid_constraints_schema")
    if result <= 0:
        raise CanaryCaptureError("invalid_constraints_schema")
    return result


def _api_state(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value == "true":
            return True
        if value == "false":
            return False
    raise CanaryCaptureError("invalid_constraints_schema")


def _write_bundle(root: Path, documents: _CapturedDocuments) -> str:
    if not isinstance(root, Path) or root.name != ARTIFACT_DIRECTORY_NAME:
        raise CanaryCaptureError("artifact_directory_invalid")
    capture_root = root / CAPTURE_DIRECTORY_NAME
    final = capture_root / documents.capture_id
    temporary = capture_root / f".tmp-{uuid.uuid4().hex[:12]}"
    written: list[Path] = []
    try:
        for path in (root, capture_root):
            if path.exists() and (not path.is_dir() or path.is_symlink()):
                raise CanaryCaptureError("artifact_directory_invalid")
            path.mkdir(exist_ok=True)
        if final.exists() or final.is_symlink():
            raise CanaryCaptureError("artifact_conflict")
        temporary.mkdir()
        for name, content in documents.files:
            path = temporary / name
            with path.open("x", encoding="utf-8", newline="") as stream:
                stream.write(content)
            written.append(path)
        manifest_path = temporary / _MANIFEST_FILENAME
        with manifest_path.open("x", encoding="utf-8", newline="") as stream:
            stream.write(documents.manifest)
        written.append(manifest_path)
        temporary.rename(final)
    except CanaryCaptureError:
        _clean_temporary(temporary, written)
        raise
    except OSError:
        _clean_temporary(temporary, written)
        raise CanaryCaptureError("artifact_write_failed") from None
    return f"{ARTIFACT_DIRECTORY_NAME}/{CAPTURE_DIRECTORY_NAME}/{documents.capture_id}"


def _clean_temporary(directory: Path, written: Sequence[Path]) -> None:
    for path in reversed(written):
        try:
            if path.parent == directory and path.exists() and not path.is_symlink():
                path.unlink()
        except OSError:
            pass
    try:
        if directory.exists() and directory.is_dir() and not directory.is_symlink():
            directory.rmdir()
    except OSError:
        pass


def _preparation_command(directory: str, digests: Mapping[str, str]) -> str:
    return (
        "python scripts/bingx_vst_prepare_intent.py "
        f'--market-input "{directory}/market-input.json" '
        f'--market-digest "{digests["market-input.json"]}" '
        f'--account-input "{directory}/account-input.json" '
        f'--account-digest "{digests["account-input.json"]}" '
        f'--constraints-input "{directory}/constraints-input.json" '
        f'--constraints-digest "{digests["constraints-input.json"]}" '
        f'--policy-input "{directory}/policy-input.json" '
        f'--policy-digest "{digests["policy-input.json"]}"'
    )


def _dry_run_command(host: str) -> str:
    return (
        "python scripts/bingx_vst_demo_order.py "
        '--intent-file "<READY_REPORT_ARTIFACT_PATH>" '
        '--intent-digest "<READY_REPORT_INTENT_DIGEST>" '
        f"--host {host}"
    )


def _readiness_reason(report: VstReadinessReport) -> str:
    if report.reason_codes:
        reason = report.reason_codes[0]
        if reason.replace("_", "").isalnum():
            return f"readiness_{reason}"
    return "readiness_failed"


def _utc_day_start_ms(timestamp_ms: int) -> int:
    value = datetime.fromtimestamp(timestamp_ms / 1_000, UTC)
    start = value.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start.timestamp() * 1_000)


def _timestamp(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1_000, UTC).isoformat().replace(
        "+00:00", "Z"
    )


def _datetime_ms(value: datetime) -> int:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise CanaryCaptureError("invalid_candle_schema")
    return int(value.astimezone(UTC).timestamp() * 1_000)


def _clock_value(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise CanaryCaptureError("invalid_clock")
    return value


def _vst_host(value: object) -> str:
    if not isinstance(value, str):
        raise CanaryCaptureError("host_not_vst")
    host = value.rstrip("/")
    if host not in VST_BASE_URLS:
        raise CanaryCaptureError("host_not_vst")
    return host


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _required_text(value: object, reason: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CanaryCaptureError(reason)
    return value.strip()


def _integer(value: object, reason: str) -> int:
    if isinstance(value, bool):
        raise CanaryCaptureError(reason)
    try:
        result = int(str(value))
    except (TypeError, ValueError):
        raise CanaryCaptureError(reason) from None
    if result < 0:
        raise CanaryCaptureError(reason)
    return result


def _decimal(value: object, reason: str) -> Decimal:
    if isinstance(value, bool):
        raise CanaryCaptureError(reason)
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise CanaryCaptureError(reason) from None
    if not result.is_finite():
        raise CanaryCaptureError(reason)
    return result.normalize()


def _non_negative_decimal(value: object, reason: str) -> Decimal:
    result = _decimal(value, reason)
    if result < 0:
        raise CanaryCaptureError(reason)
    return result


def _json_number(value: Decimal) -> int | float:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise CanaryCaptureError("invalid_candle_schema")
    if value == value.to_integral_value():
        return int(value)
    result = float(value)
    if not isfinite(result):
        raise CanaryCaptureError("invalid_candle_schema")
    return result


__all__ = (
    "AsyncCanaryCaptureTransport",
    "BingXAsyncCanaryCaptureAdapter",
    "CANARY_SYMBOL",
    "CANARY_TIMEFRAME",
    "CAPTURE_DIRECTORY_NAME",
    "CAPTURE_MANIFEST_SCHEMA_VERSION",
    "CAPTURE_POLICY_VERSION",
    "CAPTURE_STATUS",
    "CanaryCaptureError",
    "CanaryCaptureReport",
    "CapturedBalance",
    "CapturedIncome",
    "capture_canary_inputs",
    "create_async_canary_capture_transport",
)
