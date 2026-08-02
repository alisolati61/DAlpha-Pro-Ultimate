from __future__ import annotations

import hashlib
import json
import socket
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

import pytest

from src.data.adapters.recorded import RecordedExchangeMarketDataAdapter
from src.data.service import MarketDataService
from src.decision.recorded import DecisionService
from src.exchange.bingx_client import BingXHttpClient
from src.execution_intent.models import IntentStatus
from src.execution_intent.service import ExecutionIntentService
from src.risk.risk_orchestrator import RiskOrchestrator
from src.strategy.service import StrategyService
from src.vst_runtime.demo_order import (
    DEFAULT_DEMO_CANARY_POLICY,
    load_canonical_ready_intent,
)
from src.vst_runtime.intent_preparation import (
    ACCOUNT_SCHEMA_VERSION,
    ARTIFACT_DIRECTORY_NAME,
    CONSTRAINTS_SCHEMA_VERSION,
    MARKET_SCHEMA_VERSION,
    POLICY_SCHEMA_VERSION,
    IntentPreparationError,
    IntentPreparationReport,
    prepare_demo_canary_intent,
)

NOW_MS = 1_900_000_000_000


def canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def timestamp(offset_ms: int = 0) -> str:
    value = datetime.fromtimestamp((NOW_MS + offset_ms) / 1_000, UTC)
    return value.isoformat().replace("+00:00", "Z")


def canonical_documents() -> dict[str, dict[str, Any]]:
    candles = [
        [timestamp(-120_000), 99, 101, 98, 100, 1],
        [timestamp(-60_000), 100, 102, 99, 101, 1],
        [timestamp(), 101, 103, 100, 102, 1],
    ]
    return {
        "market": {
            "events": [
                {
                    "kind": "candles",
                    "payload": {
                        "candles": candles,
                        "symbol": "BTC-USDT",
                        "timeframe": "1m",
                    },
                    "sequence": 1,
                }
            ],
            "exchange": "bingx",
            "schema_version": MARKET_SCHEMA_VERSION,
            "symbol": "BTC-USDT",
            "timeframe": "1m",
        },
        "account": {
            "available_balance": "100",
            "current_exposure": "0",
            "equity": "100",
            "observed_at": timestamp(),
            "open_position_quantity": "0",
            "portfolio": {
                "balance": "100",
                "daily_loss": "0",
                "equity": "100",
                "open_positions": 0,
                "total_risk": "0",
                "used_margin": "0",
            },
            "risk_state": {
                "circuit_breaker_consecutive_losses": 0,
                "kill_switch_active": False,
            },
            "schema_version": ACCOUNT_SCHEMA_VERSION,
        },
        "constraints": {
            "exchange": "bingx",
            "maximum_quantity": "0.1",
            "minimum_notional": "1",
            "minimum_quantity": "0.001",
            "observed_at": timestamp(),
            "price_tick": "0.1",
            "quantity_step": "0.001",
            "schema_version": CONSTRAINTS_SCHEMA_VERSION,
            "symbol": "BTC-USDT",
        },
        "policy": {
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
        },
    }


def serialized_documents(
    documents: dict[str, dict[str, Any]] | None = None,
) -> dict[str, str]:
    selected = canonical_documents() if documents is None else documents
    return {name: canonical(value) for name, value in selected.items()}


def preparation_arguments(serialized: dict[str, str]) -> dict[str, str]:
    return {
        "account_digest": hashlib.sha256(serialized["account"].encode()).hexdigest(),
        "account_json": serialized["account"],
        "constraints_digest": hashlib.sha256(
            serialized["constraints"].encode()
        ).hexdigest(),
        "constraints_json": serialized["constraints"],
        "market_digest": hashlib.sha256(serialized["market"].encode()).hexdigest(),
        "market_json": serialized["market"],
        "policy_digest": hashlib.sha256(serialized["policy"].encode()).hexdigest(),
        "policy_json": serialized["policy"],
    }


def artifact_directory(tmp_path: Path, label: str | None = None) -> Path:
    parent = tmp_path if label is None else tmp_path / label
    parent.mkdir(exist_ok=True)
    return parent / ARTIFACT_DIRECTORY_NAME


def prepare(
    tmp_path: Path,
    *,
    documents: dict[str, dict[str, Any]] | None = None,
    label: str | None = None,
) -> tuple[IntentPreparationReport, Path]:
    serialized = serialized_documents(documents)
    directory = artifact_directory(tmp_path, label)
    report = prepare_demo_canary_intent(
        **preparation_arguments(serialized),
        artifact_directory=directory,
        clock_ms=lambda: NOW_MS,
    )
    return report, directory


def artifact_file(report: IntentPreparationReport, directory: Path) -> Path:
    assert report.artifact_path is not None
    return directory / Path(report.artifact_path).name


def test_ready_pipeline_writes_exact_deterministic_loader_compatible_bytes(
    tmp_path: Path,
) -> None:
    report, directory = prepare(tmp_path)

    assert report.status == IntentStatus.READY.value
    assert report.symbol == "BTC-USDT"
    assert report.side == "BUY"
    assert report.reason_codes == ("intent_ready",)
    assert report.intent_digest is not None
    path = artifact_file(report, directory)
    content = path.read_bytes()
    assert content == content.strip()
    assert hashlib.sha256(content).hexdigest() == report.intent_digest

    intent, verified_digest = load_canonical_ready_intent(
        content.decode("utf-8"), report.intent_digest
    )
    assert intent.status is IntentStatus.READY
    assert intent.symbol == "BTC-USDT"
    assert intent.exchange == "bingx"
    assert intent.to_json().encode("utf-8") == content
    assert verified_digest == report.intent_digest

    rendered = report.to_json() + content.decode("utf-8")
    for forbidden in (
        "available_balance",
        "current_exposure",
        "equity",
        "open_position_quantity",
        "portfolio",
        "used_margin",
    ):
        assert forbidden not in rendered


def _record_method(
    monkeypatch: pytest.MonkeyPatch,
    ledger: list[str],
    owner: type[Any],
    method_name: str,
    label: str,
) -> None:
    original = getattr(owner, method_name)

    def recorded(self: object, *args: object, **kwargs: object) -> object:
        ledger.append(label)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(owner, method_name, recorded)


def test_pipeline_invokes_frozen_services_once_and_closes_in_reverse_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    service_types = (
        (MarketDataService, "market"),
        (RecordedExchangeMarketDataAdapter, "adapter"),
        (StrategyService, "strategy"),
        (DecisionService, "decision"),
        (ExecutionIntentService, "intent"),
    )
    for owner, label in service_types:
        for method in ("initialize", "start", "stop"):
            _record_method(
                monkeypatch,
                calls,
                owner,
                method,
                f"{label}.{method}",
            )
    for owner, method, label in (
        (RecordedExchangeMarketDataAdapter, "replay", "adapter.replay"),
        (StrategyService, "evaluate", "strategy.evaluate"),
        (DecisionService, "evaluate", "decision.evaluate"),
        (RiskOrchestrator, "evaluate_trade", "risk.evaluate_trade"),
        (ExecutionIntentService, "construct", "intent.construct"),
    ):
        _record_method(monkeypatch, calls, owner, method, label)

    report, _directory = prepare(tmp_path)

    assert report.status == IntentStatus.READY.value
    assert calls == [
        "market.initialize",
        "market.start",
        "adapter.initialize",
        "adapter.start",
        "strategy.initialize",
        "strategy.start",
        "adapter.replay",
        "strategy.evaluate",
        "decision.initialize",
        "decision.start",
        "intent.initialize",
        "intent.start",
        "decision.evaluate",
        "risk.evaluate_trade",
        "intent.construct",
        "intent.stop",
        "decision.stop",
        "strategy.stop",
        "adapter.stop",
        "market.stop",
    ]


@pytest.mark.parametrize(
    ("case", "expected_status", "expected_reason"),
    (
        ("hold", IntentStatus.NO_ACTION.value, "decision_hold"),
        ("risk_rejected", IntentStatus.NO_ACTION.value, "decision_rejected"),
        ("blocked", IntentStatus.BLOCKED.value, "insufficient_balance"),
    ),
)
def test_nonready_pipeline_results_never_create_an_artifact(
    tmp_path: Path,
    case: str,
    expected_status: str,
    expected_reason: str,
) -> None:
    documents = canonical_documents()
    if case == "hold":
        documents["market"]["events"][0]["payload"]["candles"] = documents[
            "market"
        ]["events"][0]["payload"]["candles"][:2]
    elif case == "risk_rejected":
        documents["account"]["risk_state"]["kill_switch_active"] = True
    else:
        documents["account"]["available_balance"] = "0"

    report, directory = prepare(tmp_path, documents=documents, label=case)

    assert report.status == expected_status
    assert expected_reason in report.reason_codes
    assert report.artifact_path is None
    assert report.intent_digest is None
    assert not directory.exists()


@pytest.mark.parametrize("source", ("market", "account", "constraints"))
def test_stale_authoritative_input_fails_before_pipeline_or_artifact(
    tmp_path: Path,
    source: str,
) -> None:
    documents = canonical_documents()
    stale = timestamp(-300_001)
    if source == "market":
        candles = documents["market"]["events"][0]["payload"]["candles"]
        for index, candle in enumerate(candles):
            candle[0] = timestamp(-420_001 + (index * 60_000))
    else:
        documents[source]["observed_at"] = stale
    directory = artifact_directory(tmp_path, source)
    serialized = serialized_documents(documents)

    with pytest.raises(
        IntentPreparationError, match="Intent preparation failed"
    ) as caught:
        prepare_demo_canary_intent(
            **preparation_arguments(serialized),
            artifact_directory=directory,
            clock_ms=lambda: NOW_MS,
        )
    assert caught.value.reason_code == "stale_input"
    assert not directory.exists()


@pytest.mark.parametrize(
    ("source", "mutation", "reason"),
    (
        ("market", "pretty", "invalid_market_input_not_canonical"),
        ("account", "extra", "invalid_account_input"),
        ("constraints", "sensitive", "invalid_constraints_input"),
        ("policy", "number", "invalid_policy_input"),
    ),
)
def test_malformed_or_sensitive_canonical_inputs_fail_without_artifact(
    tmp_path: Path,
    source: str,
    mutation: str,
    reason: str,
) -> None:
    documents = canonical_documents()
    serialized = serialized_documents(documents)
    if mutation == "pretty":
        serialized[source] = json.dumps(documents[source], indent=2, sort_keys=True)
    elif mutation == "extra":
        documents[source]["unexpected"] = "value"
        serialized[source] = canonical(documents[source])
    elif mutation == "sensitive":
        documents[source]["api_secret"] = "fake-secret"
        serialized[source] = canonical(documents[source])
    else:
        documents[source]["execution"]["risk_percent"] = 0.1
        serialized[source] = canonical(documents[source])
    directory = artifact_directory(tmp_path, source)

    with pytest.raises(IntentPreparationError) as caught:
        prepare_demo_canary_intent(
            **preparation_arguments(serialized),
            artifact_directory=directory,
            clock_ms=lambda: NOW_MS,
        )
    assert caught.value.reason_code == reason
    assert "fake-secret" not in repr(caught.value)
    assert not directory.exists()


@pytest.mark.parametrize(
    ("source", "reason"),
    (
        ("market", "market_input_digest_mismatch"),
        ("account", "account_input_digest_mismatch"),
        ("constraints", "constraints_input_digest_mismatch"),
        ("policy", "policy_input_digest_mismatch"),
    ),
)
def test_source_digest_mismatch_fails_without_artifact(
    tmp_path: Path,
    source: str,
    reason: str,
) -> None:
    serialized = serialized_documents()
    arguments = preparation_arguments(serialized)
    arguments[f"{source}_digest"] = "0" * 64
    directory = artifact_directory(tmp_path, source)
    with pytest.raises(IntentPreparationError) as caught:
        prepare_demo_canary_intent(
            **arguments,
            artifact_directory=directory,
            clock_ms=lambda: NOW_MS,
        )
    assert caught.value.reason_code == reason
    assert not directory.exists()


def test_unsupported_symbol_fails_before_pipeline_or_artifact(tmp_path: Path) -> None:
    documents = canonical_documents()
    documents["market"]["symbol"] = "ETH-USDT"
    documents["market"]["events"][0]["payload"]["symbol"] = "ETH-USDT"
    documents["constraints"]["symbol"] = "ETH-USDT"
    serialized = serialized_documents(documents)
    directory = artifact_directory(tmp_path)
    with pytest.raises(IntentPreparationError) as caught:
        prepare_demo_canary_intent(
            **preparation_arguments(serialized),
            artifact_directory=directory,
            clock_ms=lambda: NOW_MS,
        )
    assert caught.value.reason_code == "unsupported_symbol"
    assert not directory.exists()


@pytest.mark.parametrize(
    "changed_input", ("market", "account", "constraints", "policy")
)
def test_every_canonical_input_is_bound_into_the_intent_digest(
    tmp_path: Path,
    changed_input: str,
) -> None:
    baseline, baseline_directory = prepare(tmp_path, label="baseline")
    documents = canonical_documents()
    if changed_input == "market":
        documents["market"]["events"][0]["payload"]["candles"][-1][4] = 101.9
    elif changed_input == "account":
        documents["account"].update(
            {"available_balance": "101", "equity": "101"}
        )
        documents["account"]["portfolio"].update(
            {"balance": "101", "equity": "101"}
        )
    elif changed_input == "constraints":
        documents["constraints"]["maximum_quantity"] = "0.09"
    else:
        documents["policy"]["execution"]["maximum_exposure_ratio"] = "0.9"

    changed, changed_directory = prepare(
        tmp_path,
        documents=documents,
        label=f"changed-{changed_input}",
    )

    assert baseline.status == changed.status == IntentStatus.READY.value
    assert baseline.intent_digest != changed.intent_digest
    assert artifact_file(baseline, baseline_directory).read_bytes() != artifact_file(
        changed, changed_directory
    ).read_bytes()


def test_paths_and_validation_clock_do_not_affect_artifact_or_expiry(
    tmp_path: Path,
) -> None:
    first, first_directory = prepare(tmp_path, label="first-runtime")
    serialized = serialized_documents()
    second_directory = artifact_directory(tmp_path, "second-runtime")
    second = prepare_demo_canary_intent(
        **preparation_arguments(serialized),
        artifact_directory=second_directory,
        clock_ms=lambda: NOW_MS + 1_000,
    )
    assert first == second
    assert artifact_file(first, first_directory).read_bytes() == artifact_file(
        second, second_directory
    ).read_bytes()
    assert first.expires_at == timestamp(300_000)


def test_artifact_directory_is_restricted_idempotent_and_never_overwritten(
    tmp_path: Path,
) -> None:
    serialized = serialized_documents()
    invalid_directory = tmp_path / "not-operator-artifacts"
    with pytest.raises(IntentPreparationError) as invalid:
        prepare_demo_canary_intent(
            **preparation_arguments(serialized),
            artifact_directory=invalid_directory,
            clock_ms=lambda: NOW_MS,
        )
    assert invalid.value.reason_code == "artifact_directory_invalid"
    assert not invalid_directory.exists()

    first, directory = prepare(tmp_path)
    path = artifact_file(first, directory)
    original = path.read_bytes()
    second, _ = prepare(tmp_path)
    assert second == first
    assert tuple(directory.glob("*.json")) == (path,)
    assert path.read_bytes() == original

    path.write_bytes(b"{}")
    with pytest.raises(IntentPreparationError) as conflict:
        prepare(tmp_path)
    assert conflict.value.reason_code == "artifact_conflict"
    assert path.read_bytes() == b"{}"


def test_unrelated_candle_identity_and_noncanonical_time_are_rejected(
    tmp_path: Path,
) -> None:
    for label, mutate in (
        (
            "identity",
            lambda documents: documents["market"]["events"][0]["payload"].update(
                {"symbol": "ETH-USDT"}
            ),
        ),
        (
            "timestamp",
            lambda documents: documents["market"]["events"][0]["payload"][
                "candles"
            ][-1].__setitem__(0, timestamp().replace("Z", "+00:00")),
        ),
    ):
        documents = canonical_documents()
        mutate(documents)
        directory = artifact_directory(tmp_path, label)
        serialized = serialized_documents(documents)
        with pytest.raises(IntentPreparationError) as caught:
            prepare_demo_canary_intent(
                **preparation_arguments(serialized),
                artifact_directory=directory,
                clock_ms=lambda: NOW_MS,
            )
        assert caught.value.reason_code == "invalid_market_input"
        assert not directory.exists()


def test_clock_is_rechecked_after_pipeline_before_artifact(tmp_path: Path) -> None:
    serialized = serialized_documents()
    directory = artifact_directory(tmp_path)
    readings = iter((NOW_MS, NOW_MS + 300_001))
    with pytest.raises(IntentPreparationError) as caught:
        prepare_demo_canary_intent(
            **preparation_arguments(serialized),
            artifact_directory=directory,
            clock_ms=lambda: next(readings),
        )
    assert caught.value.reason_code == "stale_input"
    assert not directory.exists()


def test_fixed_canary_leverage_and_notional_caps_are_enforced(
    tmp_path: Path,
) -> None:
    leverage_documents = canonical_documents()
    leverage_documents["policy"]["execution"]["leverage"] = "1"
    leverage_directory = artifact_directory(tmp_path, "leverage")
    leverage_serialized = serialized_documents(leverage_documents)
    with pytest.raises(IntentPreparationError) as leverage_error:
        prepare_demo_canary_intent(
            **preparation_arguments(leverage_serialized),
            artifact_directory=leverage_directory,
            clock_ms=lambda: NOW_MS,
        )
    assert leverage_error.value.reason_code == "canary_leverage_policy_required"
    assert not leverage_directory.exists()

    notional_documents = canonical_documents()
    notional_documents["policy"]["execution"]["risk_percent"] = "1"
    notional_documents["policy"]["risk_limits"]["max_position_size"] = "1"
    notional_documents["constraints"]["maximum_quantity"] = "1"
    report, notional_directory = prepare(
        tmp_path,
        documents=notional_documents,
        label="notional",
    )
    assert report.status == IntentStatus.READY.value
    intent_path = artifact_file(report, notional_directory)
    assert report.intent_digest is not None
    intent, _digest = load_canonical_ready_intent(
        intent_path.read_text(encoding="utf-8"),
        report.intent_digest,
    )
    assert intent.entry is not None
    assert intent.entry.quantity == Decimal("0.098")
    assert (
        intent.entry.price * intent.entry.quantity
        <= DEFAULT_DEMO_CANARY_POLICY.maximum_notional
    )


def test_large_vst_equity_is_capped_before_the_exact_risk_evaluation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    documents = canonical_documents()
    documents["market"]["events"][0]["payload"]["candles"] = [
        [timestamp(-120_000), 62_800, 63_000, 62_700, 62_900, 1],
        [timestamp(-60_000), 62_900, 63_200, 62_900, 63_100, 1],
        [timestamp(), 63_100, 63_300, 63_000, 63_200, 1],
    ]
    documents["account"].update(
        {"available_balance": "180000", "equity": "180000"}
    )
    documents["account"]["portfolio"].update(
        {"balance": "180000", "equity": "180000"}
    )
    documents["constraints"].update(
        {
            "maximum_quantity": None,
            "minimum_notional": "2",
            "minimum_quantity": "0.0001",
            "quantity_step": "0.0001",
        }
    )
    observed_sizes: list[float] = []
    evaluate_trade = RiskOrchestrator.evaluate_trade

    def observe_risk_call(
        self: RiskOrchestrator,
        **kwargs: Any,
    ) -> Any:
        observed_sizes.append(kwargs["position_size"])
        return evaluate_trade(self, **kwargs)

    monkeypatch.setattr(RiskOrchestrator, "evaluate_trade", observe_risk_call)

    report, directory = prepare(
        tmp_path,
        documents=documents,
        label="large-vst-equity",
    )

    assert report.status == IntentStatus.READY.value
    assert report.intent_digest is not None
    intent, _digest = load_canonical_ready_intent(
        artifact_file(report, directory).read_text(encoding="utf-8"),
        report.intent_digest,
    )
    assert intent.entry is not None
    assert intent.entry.quantity == Decimal("0.0001")
    assert observed_sizes == [float(intent.entry.quantity)]
    assert (
        intent.entry.price * intent.entry.quantity
        <= DEFAULT_DEMO_CANARY_POLICY.maximum_notional
    )


def test_below_cap_nonstep_quantity_is_normalized_before_risk_evaluation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    documents = canonical_documents()
    documents["account"].update({"available_balance": "101", "equity": "101"})
    documents["account"]["portfolio"].update(
        {"balance": "101", "equity": "101"}
    )
    observed_sizes: list[float] = []
    evaluate_trade = RiskOrchestrator.evaluate_trade

    def observe_risk_call(
        self: RiskOrchestrator,
        **kwargs: Any,
    ) -> Any:
        observed_sizes.append(kwargs["position_size"])
        return evaluate_trade(self, **kwargs)

    monkeypatch.setattr(RiskOrchestrator, "evaluate_trade", observe_risk_call)

    report, directory = prepare(
        tmp_path,
        documents=documents,
        label="nonstep-risk",
    )

    assert report.status == IntentStatus.READY.value
    assert report.intent_digest is not None
    intent, _digest = load_canonical_ready_intent(
        artifact_file(report, directory).read_text(encoding="utf-8"),
        report.intent_digest,
    )
    assert intent.entry is not None
    assert intent.entry.quantity == Decimal("0.05")
    assert observed_sizes == [float(intent.entry.quantity)]


def test_capped_sizing_digest_is_independent_of_decimal_context(
    tmp_path: Path,
) -> None:
    documents = canonical_documents()
    documents["policy"]["execution"]["risk_percent"] = "1"
    documents["policy"]["risk_limits"]["max_position_size"] = "1"
    documents["constraints"]["maximum_quantity"] = "1"

    with localcontext() as context:
        context.prec = 9
        first, first_directory = prepare(
            tmp_path,
            documents=documents,
            label="decimal-context-9",
        )
    with localcontext() as context:
        context.prec = 28
        second, second_directory = prepare(
            tmp_path,
            documents=documents,
            label="decimal-context-28",
        )

    assert first == second
    assert artifact_file(first, first_directory).read_bytes() == artifact_file(
        second,
        second_directory,
    ).read_bytes()


def test_exchange_minimum_above_canary_cap_stays_fail_closed(
    tmp_path: Path,
) -> None:
    documents = canonical_documents()
    documents["constraints"]["minimum_notional"] = "11"

    report, directory = prepare(
        tmp_path,
        documents=documents,
        label="minimum-above-cap",
    )

    assert report.status == IntentStatus.BLOCKED.value
    assert report.reason_codes == ("notional_below_minimum",)
    assert report.artifact_path is None
    assert not directory.exists()


def test_preparation_has_no_exchange_network_or_write_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("external side effect")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    for method_name in ("request", "place_order", "cancel_order"):
        monkeypatch.setattr(BingXHttpClient, method_name, forbidden)

    report, directory = prepare(tmp_path)

    assert report.status == IntentStatus.READY.value
    assert tuple(directory.iterdir()) == (artifact_file(report, directory),)


def test_report_failure_is_canonical_and_contains_no_input_values() -> None:
    report = IntentPreparationReport.failure("invalid_account_input")
    rendered = report.to_json()
    assert rendered == canonical(report.to_dict())
    assert json.loads(rendered)["status"] == IntentStatus.BLOCKED.value
    for forbidden in (
        "available_balance",
        "current_exposure",
        "equity",
        "portfolio",
        "api_key",
        "api_secret",
    ):
        assert forbidden not in rendered
