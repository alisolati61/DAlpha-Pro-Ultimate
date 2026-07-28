"""Safe command-line interface for Alpha Pro X Infinity."""

from __future__ import annotations

import argparse
import asyncio
import sys
from importlib import metadata
from typing import Sequence

from src.core.kernel.bootstrap import build_runtime
from src.core.kernel.runtime import RuntimeMode
from src.core.kernel.state import KernelState

_DISTRIBUTION_NAME = "alpha-pro-x-infinity"
_MINIMUM_PYTHON = (3, 12)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alpha-pro-x",
        description="Alpha Pro X Infinity local diagnostics.",
    )
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser(
        RuntimeMode.DOCTOR.value,
        help="Run safe local diagnostics (default).",
    )
    return parser


async def _doctor() -> int:
    checks: list[tuple[str, bool]] = []
    checks.append(
        (
            "python",
            sys.version_info >= _MINIMUM_PYTHON,
        )
    )

    try:
        package_version = metadata.version(_DISTRIBUTION_NAME)
    except metadata.PackageNotFoundError:
        package_version = ""

    checks.append(("package metadata", bool(package_version)))

    runtime = build_runtime()
    checks.extend(
        (
            ("kernel construction", runtime.kernel is not None),
            ("runtime construction", runtime.mode is RuntimeMode.DOCTOR),
            (
                "exchange wiring absent",
                not hasattr(runtime, "exchange"),
            ),
            (
                "execution wiring absent",
                not hasattr(runtime, "execution"),
            ),
        )
    )

    await runtime.startup()
    checks.append(
        (
            "local startup",
            runtime.kernel.state is KernelState.RUNNING,
        )
    )
    await runtime.shutdown()
    checks.append(
        (
            "local shutdown",
            runtime.kernel.state is KernelState.SHUTDOWN,
        )
    )

    print("Alpha Pro X Infinity doctor")

    for name, passed in checks:
        status = "OK" if passed else "FAIL"
        print(f"[{status}] {name}")

    succeeded = all(passed for _, passed in checks)
    print("Doctor: OK" if succeeded else "Doctor: FAILED")
    return 0 if succeeded else 1


def main(argv: Sequence[str] | None = None) -> int:
    """Run the safe CLI; Doctor is the only accepted operating mode."""

    parser = _build_parser()
    arguments = parser.parse_args(argv)
    command = arguments.command or RuntimeMode.DOCTOR.value

    if command != RuntimeMode.DOCTOR.value:
        parser.error(f"unsupported command: {command}")

    try:
        return asyncio.run(_doctor())
    except Exception as error:
        print(
            "Doctor failed: internal check error "
            f"({type(error).__name__}).",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ("main",)
