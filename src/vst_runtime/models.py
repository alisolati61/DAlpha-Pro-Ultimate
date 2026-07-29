"""Immutable, canonical contracts for BingX VST execution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import urlsplit

from .errors import VstConfigurationError, VstValidationError

VST_BASE_URLS = frozenset(
    {"https://open-api-vst.bingx.com", "https://open-api-vst.bingx.pro"}
)


def decimal(value: object, field: str, *, allow_zero: bool = True) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise VstValidationError(f"{field} is invalid") from exc
    if not result.is_finite() or result < 0 or (not allow_zero and result == 0):
        raise VstValidationError(f"{field} is invalid")
    return result.normalize()


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VstValidationError(f"{field} is invalid")
    return value.strip()


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(
        _json_value(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    )


class RemoteOrderStatus(str, Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


class ReconciliationState(str, Enum):
    MATCHED = "MATCHED"
    MISMATCH = "MISMATCH"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class VstConfiguration:
    api_key: str
    api_secret: str
    symbols: frozenset[str]
    maximum_order_notional: Decimal
    maximum_open_positions: int
    maximum_session_loss: Decimal
    configuration_version: str
    base_url: str = "https://open-api-vst.bingx.com"
    environment: str = "VST"
    timeout_seconds: float = 10.0
    recv_window_ms: int = 5_000
    account_id: str | None = None
    kill_switch_enabled: bool = True
    maximum_exposure: Decimal | None = None
    maximum_clock_drift_ms: int = 2_000
    stale_after_ms: int = 30_000
    unknown_limit: int = 1
    failure_limit: int = 3

    def __post_init__(self) -> None:
        if self.environment != "VST":
            raise VstConfigurationError("environment must be VST")
        normalized = self.base_url.rstrip("/")
        parts = urlsplit(normalized)
        if (
            normalized not in VST_BASE_URLS
            or parts.scheme != "https"
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
        ):
            raise VstConfigurationError("base_url is not an allowlisted VST host")
        if not isinstance(self.api_key, str) or not self.api_key.strip():
            raise VstConfigurationError("api_key is required")
        if not isinstance(self.api_secret, str) or not self.api_secret.strip():
            raise VstConfigurationError("api_secret is required")
        symbols = frozenset(_text(symbol, "symbol").upper() for symbol in self.symbols)
        if not symbols:
            raise VstConfigurationError("symbols are required")
        if (
            isinstance(self.timeout_seconds, bool)
            or self.timeout_seconds <= 0
            or self.timeout_seconds > 60
        ):
            raise VstConfigurationError("timeout_seconds is invalid")
        for name, value, lower, upper in (
            ("recv_window_ms", self.recv_window_ms, 1, 5_000),
            ("maximum_open_positions", self.maximum_open_positions, 1, None),
            ("maximum_clock_drift_ms", self.maximum_clock_drift_ms, 0, None),
            ("stale_after_ms", self.stale_after_ms, 1, None),
            ("unknown_limit", self.unknown_limit, 1, None),
            ("failure_limit", self.failure_limit, 1, None),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise VstConfigurationError(f"{name} is invalid")
            if value < lower or (upper is not None and value > upper):
                raise VstConfigurationError(f"{name} is invalid")
        object.__setattr__(self, "base_url", normalized)
        object.__setattr__(self, "api_key", self.api_key.strip())
        object.__setattr__(self, "api_secret", self.api_secret.strip())
        object.__setattr__(self, "symbols", symbols)
        object.__setattr__(
            self,
            "maximum_order_notional",
            decimal(
                self.maximum_order_notional, "maximum_order_notional", allow_zero=False
            ),
        )
        object.__setattr__(
            self,
            "maximum_session_loss",
            decimal(
                self.maximum_session_loss, "maximum_session_loss", allow_zero=False
            ),
        )
        if self.maximum_exposure is not None:
            object.__setattr__(
                self,
                "maximum_exposure",
                decimal(self.maximum_exposure, "maximum_exposure", allow_zero=False),
            )
        object.__setattr__(
            self,
            "configuration_version",
            _text(self.configuration_version, "configuration_version"),
        )

    @property
    def policy_id(self) -> str:
        payload = canonical(
            {
                "base_url": self.base_url,
                "configuration_version": self.configuration_version,
                "environment": self.environment,
                "maximum_exposure": self.maximum_exposure,
                "maximum_open_positions": self.maximum_open_positions,
                "maximum_order_notional": self.maximum_order_notional,
                "maximum_session_loss": self.maximum_session_loss,
                "symbols": sorted(self.symbols),
            }
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def __repr__(self) -> str:
        return (
            "VstConfiguration(environment='VST', base_url="
            f"{self.base_url!r}, symbols={sorted(self.symbols)!r}, "
            f"configuration_version={self.configuration_version!r}, "
            "api_key=<redacted>, api_secret=<redacted>)"
        )


@dataclass(frozen=True, slots=True)
class RemoteOrder:
    client_order_id: str
    order_id: str
    symbol: str
    side: str
    order_type: str
    status: RemoteOrderStatus
    original_quantity: Decimal
    filled_quantity: Decimal
    average_price: Decimal
    price: Decimal
    update_id: str
    updated_at_ms: int
    reduce_only: bool = False
    parent_client_order_id: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "client_order_id",
            "order_id",
            "symbol",
            "side",
            "order_type",
            "update_id",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in ("original_quantity", "filled_quantity", "average_price", "price"):
            object.__setattr__(self, name, decimal(getattr(self, name), name))
        if self.filled_quantity > self.original_quantity:
            raise VstValidationError("filled_quantity exceeds original_quantity")
        if not isinstance(self.updated_at_ms, int) or self.updated_at_ms < 0:
            raise VstValidationError("updated_at_ms is invalid")

    @property
    def remaining_quantity(self) -> Decimal:
        return self.original_quantity - self.filled_quantity


@dataclass(frozen=True, slots=True)
class RemoteFill:
    fill_id: str
    order_id: str
    client_order_id: str
    symbol: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    fee_asset: str
    timestamp_ms: int

    def __post_init__(self) -> None:
        for name in ("fill_id", "order_id", "client_order_id", "symbol", "fee_asset"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(
            self, "quantity", decimal(self.quantity, "quantity", allow_zero=False)
        )
        object.__setattr__(
            self, "price", decimal(self.price, "price", allow_zero=False)
        )
        object.__setattr__(self, "fee", decimal(self.fee, "fee"))


@dataclass(frozen=True, slots=True)
class RemotePosition:
    symbol: str
    side: str
    quantity: Decimal
    entry_price: Decimal
    updated_at_ms: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", _text(self.symbol, "symbol"))
        object.__setattr__(self, "side", _text(self.side, "side"))
        object.__setattr__(self, "quantity", decimal(self.quantity, "quantity"))
        object.__setattr__(
            self, "entry_price", decimal(self.entry_price, "entry_price")
        )


@dataclass(frozen=True, slots=True)
class RemoteBalance:
    asset: str
    balance: Decimal
    equity: Decimal
    available_margin: Decimal
    updated_at_ms: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "asset", _text(self.asset, "asset"))
        for name in ("balance", "equity", "available_margin"):
            object.__setattr__(self, name, decimal(getattr(self, name), name))


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    state: ReconciliationState
    reason_codes: tuple[str, ...]
    recommended_actions: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", tuple(sorted(set(self.reason_codes))))
        object.__setattr__(
            self, "recommended_actions", tuple(sorted(set(self.recommended_actions)))
        )


@dataclass(frozen=True, slots=True)
class KillSwitchState:
    active: bool = False
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VstSubmissionResult:
    intent_id: str
    client_order_id: str | None
    order: RemoteOrder | None
    accepted: bool
    reason_code: str
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class VstCheckpoint:
    policy_id: str
    accepted_intent_ids: tuple[str, ...]
    client_order_ids: tuple[tuple[str, str], ...]
    intent_digests: tuple[tuple[str, str], ...]
    orders: tuple[RemoteOrder, ...]
    fills: tuple[RemoteFill, ...]
    positions: tuple[RemotePosition, ...]
    balance: RemoteBalance | None
    reconciliation: ReconciliationResult
    kill_switch: KillSwitchState
    latest_update_id: str | None
    version: int
    digest: str = ""

    def __post_init__(self) -> None:
        data = self.to_dict(include_digest=False)
        expected = hashlib.sha256(canonical(data).encode()).hexdigest()
        if self.digest and self.digest != expected:
            raise VstValidationError("checkpoint digest is invalid")
        object.__setattr__(self, "digest", expected)

    def to_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        data = asdict(self)
        data.pop("digest", None)
        if include_digest:
            data["digest"] = self.digest
        return data


@dataclass(frozen=True, slots=True)
class VstExecutionReport:
    checkpoint: VstCheckpoint
    report_digest: str = ""

    def __post_init__(self) -> None:
        expected = hashlib.sha256(
            canonical(self.checkpoint.to_dict()).encode()
        ).hexdigest()
        if self.report_digest and self.report_digest != expected:
            raise VstValidationError("report digest is invalid")
        object.__setattr__(self, "report_digest", expected)


EMPTY_RECONCILIATION = ReconciliationResult(
    ReconciliationState.UNKNOWN,
    ("not_reconciled",),
    ("fetch_authoritative_state",),
)


def maps(checkpoint: VstCheckpoint) -> tuple[Mapping[str, str], Mapping[str, str]]:
    return (
        MappingProxyType(dict(checkpoint.client_order_ids)),
        MappingProxyType(dict(checkpoint.intent_digests)),
    )


__all__ = tuple(
    name
    for name in globals()
    if name.startswith(("Vst", "Remote", "Reconciliation", "Kill"))
) + (
    "EMPTY_RECONCILIATION",
    "VST_BASE_URLS",
)
