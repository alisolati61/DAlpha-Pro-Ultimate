"""Public-only BingX VST transport diagnostic."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence

from src.exchange.bingx_client import BingXHttpClient
from src.vst_runtime.models import VST_BASE_URLS

_PRIMARY_VST_HOST = "https://open-api-vst.bingx.com"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Diagnose the public BingX VST server-time transport."
    )
    parser.add_argument("--host", default=_PRIMARY_VST_HOST)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    return parser


async def _diagnose(host: str, timeout_seconds: float) -> dict[str, object]:
    selected_base_url = None if host == _PRIMARY_VST_HOST else host
    client = BingXHttpClient(
        api_key="",
        api_secret="",
        demo_mode=True,
        base_url=selected_base_url,
        timeout=timeout_seconds,
    )
    try:
        return (await client.diagnose_server_time()).to_dict()
    finally:
        await client.close()


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = build_parser().parse_args(argv)
        host = arguments.host.rstrip("/")
        if host not in VST_BASE_URLS:
            raise ValueError
        if arguments.timeout_seconds <= 0:
            raise ValueError
        result = asyncio.run(_diagnose(host, arguments.timeout_seconds))
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0 if result["reason_code"] == "ok" else 1
    except SystemExit:
        raise
    except Exception:
        print(
            '{"attempted_host":"unknown","exception_type":null,'
            '"reason_code":"diagnostic_configuration_invalid",'
            '"sanitized_errno":null,"server_time_ms":null,'
            '"transport_stage":"configuration"}'
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
