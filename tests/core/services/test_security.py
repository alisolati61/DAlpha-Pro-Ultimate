"""Side-effect and public-error guards for service graph imports."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from src.core.lifecycle.service import Service
from src.core.services.errors import ServiceGraphError
from src.core.services.graph import ServiceGraph
from src.core.services.models import ServiceDefinition


class NoOpService(Service):
    def initialize(self) -> None:
        return None

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None


def test_graph_errors_do_not_expose_ids_or_reprs() -> None:
    secret_id = "api_key-hidden"
    definition = ServiceDefinition(
        "worker",
        NoOpService(),
        (secret_id,),
    )

    try:
        ServiceGraph((definition,))
    except ServiceGraphError as error:
        public = str(error).casefold()
    else:
        raise AssertionError("Invalid graph was accepted.")

    assert secret_id not in public
    assert "0x" not in public
    assert "noopservice" not in public


def test_import_and_graph_construction_are_side_effect_free(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[3]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project_root)
    environment["BINGX_API_KEY"] = "must-not-be-read"
    script = (
        "import sys;"
        "import src.core.services;"
        "from src.core.services import ServiceGraph;"
        "ServiceGraph();"
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
