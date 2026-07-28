"""Safe command-line interface for Alpha Pro X Infinity."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Sequence

from src.core.diagnostics.doctor import DoctorRunner
from src.core.diagnostics.models import (
    DiagnosticReport,
    DiagnosticStatus,
)
from src.core.kernel.runtime import RuntimeMode

_TEXT_FORMAT = "text"
_JSON_FORMAT = "json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alpha-pro-x",
        description="Alpha Pro X Infinity local diagnostics.",
    )
    subcommands = parser.add_subparsers(dest="command")
    doctor_parser = subcommands.add_parser(
        RuntimeMode.DOCTOR.value,
        help="Run safe local diagnostics (default).",
    )
    doctor_parser.add_argument(
        "--format",
        choices=(_TEXT_FORMAT, _JSON_FORMAT),
        default=_TEXT_FORMAT,
        dest="output_format",
    )
    doctor_parser.add_argument(
        "--output",
        type=Path,
    )
    doctor_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing output file.",
    )
    return parser


def _format_text(report: DiagnosticReport) -> str:
    lines = [f"{report.application} doctor"]

    for check in report.checks:
        status = (
            "OK"
            if check.status is DiagnosticStatus.PASS
            else "FAIL"
        )
        lines.append(f"[{status}] {check.name}")

    lines.append(
        "Doctor: OK"
        if report.success
        else "Doctor: FAILED"
    )
    return "\n".join(lines)


def _format_report(
    report: DiagnosticReport,
    output_format: str,
) -> str:
    if output_format == _JSON_FORMAT:
        return report.to_json()

    if output_format == _TEXT_FORMAT:
        return _format_text(report)

    raise ValueError("Unsupported diagnostic output format.")


def _write_output(
    output: Path,
    payload: str,
    *,
    force: bool,
) -> None:
    mode = "w" if force else "x"

    with output.open(
        mode,
        encoding="utf-8",
        newline="\n",
    ) as stream:
        stream.write(payload)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the safe CLI; Doctor is the only accepted operating mode."""

    parser = _build_parser()
    arguments = parser.parse_args(argv)
    command = arguments.command or RuntimeMode.DOCTOR.value

    if command == RuntimeMode.DOCTOR.value and arguments.command is None:
        arguments.output_format = _TEXT_FORMAT
        arguments.output = None
        arguments.force = False

    if command != RuntimeMode.DOCTOR.value:
        parser.error(f"unsupported command: {command}")

    if arguments.force and arguments.output is None:
        parser.error("--force requires --output")

    try:
        report = asyncio.run(DoctorRunner().run())
        payload = _format_report(
            report,
            arguments.output_format,
        )

        if arguments.output is None:
            print(payload)
        else:
            _write_output(
                arguments.output,
                payload,
                force=arguments.force,
            )
    except (OSError, TypeError, ValueError):
        print(
            "Doctor failed: report output unavailable.",
            file=sys.stderr,
        )
        return 1
    except Exception:
        print(
            "Doctor failed: internal diagnostic error.",
            file=sys.stderr,
        )
        return 1

    return 0 if report.success else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ("main",)
