"""Tests for immutable canonical recorded payload contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from math import nan

import pytest

from src.data.adapters.errors import InvalidRecordedPayloadError
from src.data.adapters.models import (
    RecordedMarketDataPayload,
    RecordedPayloadKind,
    ReplayResult,
)


def test_mapping_is_canonical_defensive_and_deterministic() -> None:
    source = {
        "symbol": "BTCUSDT",
        "levels": [[100, 1]],
        "metadata": {"source": "recorded"},
    }
    payload = RecordedMarketDataPayload.from_mapping(
        sequence=1,
        kind=RecordedPayloadKind.ORDER_BOOK,
        payload=source,
    )
    first_digest = payload.digest

    source["symbol"] = "MUTATED"
    source["levels"][0][0] = 999
    decoded = payload.to_mapping()
    decoded["symbol"] = "RETURNED-MUTATION"

    assert payload.to_mapping()["symbol"] == "BTCUSDT"
    assert payload.to_mapping()["levels"] == [[100, 1]]
    assert payload.digest == first_digest
    assert len(payload.digest) == 64


def test_contracts_are_immutable() -> None:
    payload = RecordedMarketDataPayload.from_mapping(
        sequence=0,
        kind=RecordedPayloadKind.CANDLES,
        payload={"candles": []},
    )
    result = ReplayResult(0, None, ())

    with pytest.raises(FrozenInstanceError):
        payload.sequence = 2  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.applied = 1  # type: ignore[misc]


@pytest.mark.parametrize("sequence", [-1, True, 1.5, "1"])
def test_sequence_is_non_negative_integer(sequence: object) -> None:
    with pytest.raises(InvalidRecordedPayloadError):
        RecordedMarketDataPayload.from_mapping(
            sequence=sequence,  # type: ignore[arg-type]
            kind=RecordedPayloadKind.SNAPSHOT,
            payload={},
        )


def test_direct_payload_requires_canonical_json() -> None:
    with pytest.raises(InvalidRecordedPayloadError):
        RecordedMarketDataPayload(
            1,
            RecordedPayloadKind.SNAPSHOT,
            '{"z": 1, "a": 2}',
        )
    with pytest.raises(InvalidRecordedPayloadError):
        RecordedMarketDataPayload(
            1,
            RecordedPayloadKind.SNAPSHOT,
            "not-json",
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"api_key": "hidden"},
        {"nested": {"password": "hidden"}},
        {"value": nan},
        {"value": object()},
    ],
)
def test_unsafe_or_non_json_payloads_are_rejected(
    payload: dict[str, object],
) -> None:
    with pytest.raises(InvalidRecordedPayloadError) as captured:
        RecordedMarketDataPayload.from_mapping(
            sequence=1,
            kind=RecordedPayloadKind.SNAPSHOT,
            payload=payload,
        )

    public = str(captured.value).casefold()
    assert "hidden" not in public
    assert "object at" not in public


def test_replay_result_validates_aggregate_fields() -> None:
    with pytest.raises(ValueError):
        ReplayResult(1, 1, ())
    with pytest.raises(ValueError):
        ReplayResult(0, -1, ())
