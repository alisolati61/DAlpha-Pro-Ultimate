from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_import_and_empty_lifecycle_are_side_effect_free(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[3]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project_root)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["BINGX_API_KEY"] = "must-not-be-read"
    environment["BINGX_API_SECRET"] = "must-not-be-read"
    script = (
        "import os,socket,threading;"
        "before=tuple(threading.enumerate());"
        "blocked=lambda *args,**kwargs:(_ for _ in ()).throw("
        "AssertionError('forbidden import side effect'));"
        "os.getenv=blocked;"
        "socket.socket=blocked;"
        "socket.create_connection=blocked;"
        "from src.paper_runtime import (PaperAccountSnapshot,"
        "PaperExecutionCoordinator,PaperExecutionPolicy);"
        "policy=PaperExecutionPolicy('import-v1','0','0','1','0.01','1');"
        "account=PaperAccountSnapshot("
        "'100','100','100','0','0','0','0','0',0);"
        "service=PaperExecutionCoordinator(policy,account);"
        "service.initialize();service.start();service.stop();"
        "assert tuple(threading.enumerate()) == before"
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
