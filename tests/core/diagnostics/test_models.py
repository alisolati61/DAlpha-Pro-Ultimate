"""Contract tests for immutable public diagnostic models."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from math import inf, nan

import pytest

from src.core.diagnostics.models import (
    DiagnosticCheck,
    DiagnosticReport,
    DiagnosticStatus,
)


def make_check(
    *,
    status: DiagnosticStatus = DiagnosticStatus.PASS,
) -> DiagnosticCheck:
    return DiagnosticCheck(
        name="python",
        status=status,
        message="Python requirement satisfied.",
        duration_ms=1.25,
    )


def make_report() -> DiagnosticReport:
    started = datetime(2026, 1, 1, tzinfo=UTC)
    return DiagnosticReport(
        application="Alpha Pro X Infinity",
        version="0.1.0",
        mode="doctor",
        success=True,
        started_at=started,
        finished_at=started + timedelta(seconds=1),
        duration_ms=1000.0,
        checks=(make_check(),),
    )


def test_contracts_are_immutable() -> None:
    check = make_check()
    report = make_report()

    with pytest.raises(FrozenInstanceError):
        check.name = "changed"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        report.success = False  # type: ignore[misc]


@pytest.mark.parametrize("name", ["", " ", "\n"])
def test_check_requires_non_empty_name(name: str) -> None:
    with pytest.raises(ValueError, match="name cannot be empty"):
        DiagnosticCheck(
            name=name,
            status=DiagnosticStatus.PASS,
            message="Safe message.",
            duration_ms=0,
        )


@pytest.mark.parametrize("duration", [-1, nan, inf, -inf])
def test_durations_must_be_finite_and_non_negative(
    duration: float,
) -> None:
    with pytest.raises(ValueError, match="finite and non-negative"):
        DiagnosticCheck(
            name="duration",
            status=DiagnosticStatus.PASS,
            message="Safe message.",
            duration_ms=duration,
        )


def test_report_normalizes_timestamps_to_utc() -> None:
    local_timezone = timezone(timedelta(hours=3, minutes=30))
    started = datetime(2026, 1, 1, tzinfo=local_timezone)
    report = DiagnosticReport(
        application="Alpha Pro X Infinity",
        version="0.1.0",
        mode="doctor",
        success=True,
        started_at=started,
        finished_at=started + timedelta(seconds=1),
        duration_ms=1000,
        checks=(make_check(),),
    )

    assert report.started_at.tzinfo is UTC
    assert report.finished_at.tzinfo is UTC


def test_report_rejects_naive_or_reversed_timestamps() -> None:
    naive = datetime(2026, 1, 1)

    with pytest.raises(ValueError, match="timezone-aware"):
        DiagnosticReport(
            application="Alpha Pro X Infinity",
            version="0.1.0",
            mode="doctor",
            success=True,
            started_at=naive,
            finished_at=naive,
            duration_ms=0,
            checks=(make_check(),),
        )

    started = datetime(2026, 1, 2, tzinfo=UTC)

    with pytest.raises(ValueError, match="cannot be earlier"):
        DiagnosticReport(
            application="Alpha Pro X Infinity",
            version="0.1.0",
            mode="doctor",
            success=True,
            started_at=started,
            finished_at=started - timedelta(seconds=1),
            duration_ms=0,
            checks=(make_check(),),
        )


def test_success_must_match_aggregate_check_status() -> None:
    started = datetime(2026, 1, 1, tzinfo=UTC)

    with pytest.raises(ValueError, match="aggregate check status"):
        DiagnosticReport(
            application="Alpha Pro X Infinity",
            version="0.1.0",
            mode="doctor",
            success=True,
            started_at=started,
            finished_at=started,
            duration_ms=0,
            checks=(make_check(status=DiagnosticStatus.FAIL),),
        )


@pytest.mark.parametrize(
    "unsafe_message",
    [
        "Traceback: internal failure",
        "api_key=do-not-expose",
        "password=do-not-expose",
        r"Failure in C:\private\project",
        "Failure in /home/private/project",
        "line one\nline two",
    ],
)
def test_public_messages_are_sanitized(
    unsafe_message: str,
) -> None:
    check = DiagnosticCheck(
        name="safe",
        status=DiagnosticStatus.FAIL,
        message=unsafe_message,
        duration_ms=0,
    )

    assert unsafe_message not in check.message
    assert "\n" not in check.message


def test_all_public_text_fields_are_sanitized() -> None:
    started = datetime(2026, 1, 1, tzinfo=UTC)
    check = DiagnosticCheck(
        name=r"C:\private\check",
        status=DiagnosticStatus.FAIL,
        message="Safe failure.",
        duration_ms=0,
    )
    report = DiagnosticReport(
        application="api_key=hidden",
        version="/home/private/version",
        mode="password=hidden",
        success=False,
        started_at=started,
        finished_at=started,
        duration_ms=0,
        checks=(check,),
    )
    payload = report.to_json().casefold()

    assert "hidden" not in payload
    assert "/home/" not in payload
    assert "c:\\private" not in payload


def test_dict_and_json_serialization_are_deterministic() -> None:
    report = make_report()

    first_dict = report.to_dict()
    second_dict = report.to_dict()
    first_json = report.to_json()
    second_json = report.to_json()

    assert first_dict == second_dict
    assert first_json == second_json
    assert json.loads(first_json) == first_dict
    assert first_dict["started_at"].endswith("Z")
    assert first_dict["checks"][0]["status"] == "pass"
