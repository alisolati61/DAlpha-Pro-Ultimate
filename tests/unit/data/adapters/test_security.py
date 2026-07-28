"""Security and side-effect guards for recorded adapter imports."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_import_initialize_and_empty_replay_are_side_effect_free(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[4]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project_root)
    environment["BINGX_API_KEY"] = "must-not-be-read"
    script = (
        "import sys,threading;"
        "before=tuple(threading.enumerate());"
        "from src.data.service import MarketDataService;"
        "from src.data.adapters.recorded import "
        "RecordedExchangeMarketDataAdapter;"
        "service=MarketDataService();service.initialize();service.start();"
        "adapter=RecordedExchangeMarketDataAdapter(service);"
        "adapter.initialize();adapter.start();adapter.replay(());"
        "assert tuple(threading.enumerate()) == before;"
        "blocked=('src.config.settings','src.logger.logger',"
        "'src.exchange','src.execution.execution_engine');"
        "assert not any(name in sys.modules for name in blocked)"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert tuple(tmp_path.iterdir()) == ()
