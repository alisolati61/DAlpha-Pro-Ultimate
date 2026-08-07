from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "phase-1l-vst-controlled-execution"


class PatchError(RuntimeError):
    pass


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise PatchError(f"git_failed:{' '.join(args)}")
    return result.stdout.strip()


def canonical(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    newline = "\r\n" if b"\r\n" in raw else "\n"
    return canonical(text), newline


def atomic_write(path: Path, text: str, newline: str) -> None:
    rendered = text if newline == "\n" else text.replace("\n", "\r\n")
    temp = path.with_name(f".{path.name}.safe-patch.tmp")
    temp.write_bytes(rendered.encode("utf-8"))
    os.replace(temp, path)


def replace_once(text: str, old: str, new: str, name: str) -> str:
    count = text.count(old)
    if count != 1:
        raise PatchError(f"{name}:expected_1_found_{count}")
    return text.replace(old, new, 1)


def precheck() -> None:
    branch = git("branch", "--show-current")
    if branch != EXPECTED_BRANCH:
        raise PatchError(f"wrong_branch:{branch}")
    if git("status", "--porcelain"):
        raise PatchError("worktree_not_clean")


def phase_1l_execute_once() -> None:
    operator_path = ROOT / "tools" / "operator.ps1"
    test_path = (
        ROOT
        / "tests"
        / "unit"
        / "vst_runtime"
        / "test_canary_rehearse_cli.py"
    )

    operator, operator_newline = read(operator_path)
    tests, tests_newline = read(test_path)

    old_param = '''param(
    [Parameter(Position = 0)]
    [ValidateSet("watch", "rehearse", "help")]
    [string]$Action = "help",

    [ValidateRange(1, 10)]
    [int]$Attempts = 1
)'''

    new_param = '''param(
    [Parameter(Position = 0)]
    [ValidateSet("watch", "rehearse", "execute-once", "help")]
    [string]$Action = "help",

    [ValidateRange(1, 10)]
    [int]$Attempts = 1,

    [string]$IntentFile = "",
    [string]$IntentDigest = "",
    [string]$PlanFile = "",
    [string]$PlanDigest = "",

    [switch]$ArmVstWrite
)'''

    operator = replace_once(
        operator,
        old_param,
        new_param,
        "operator_parameter_block",
    )

    marker = 'Write-Host "Alpha Pro VST operator"'

    execute_block = r'''if ($Action -eq "execute-once") {
    if (-not $ArmVstWrite) {
        throw "STOP: execute-once requires -ArmVstWrite"
    }

    foreach ($value in @(
        $IntentFile,
        $IntentDigest,
        $PlanFile,
        $PlanDigest
    )) {
        if ([string]::IsNullOrWhiteSpace($value)) {
            throw "STOP: execute-once arguments are incomplete"
        }
    }

    if ($IntentDigest -notmatch '^[0-9a-fA-F]{64}$') {
        throw "STOP: invalid intent digest"
    }

    if ($PlanDigest -notmatch '^[0-9a-fA-F]{64}$') {
        throw "STOP: invalid plan digest"
    }

    $intentItem = Get-Item -LiteralPath $IntentFile -ErrorAction Stop
    $planItem = Get-Item -LiteralPath $PlanFile -ErrorAction Stop

    if ($intentItem.PSIsContainer -or $planItem.PSIsContainer) {
        throw "STOP: artifact path must be a file"
    }

    if (
        (($intentItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) -or
        (($planItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)
    ) {
        throw "STOP: artifact cannot be a link/reparse point"
    }

    Write-Host ""
    Write-Host "CONTROLLED BINGX VST WRITE"
    Write-Host "HOST=https://open-api-vst.bingx.pro"
    Write-Host "MAX_SUBMISSIONS=1"
    Write-Host "AUTOMATIC_WRITE_RETRY=DISABLED"
    Write-Host "LIVE_TRADING=DISABLED"

    & $Python `
        "-m" `
        "scripts.bingx_vst_demo_order" `
        "--intent-file" `
        $intentItem.FullName `
        "--intent-digest" `
        $IntentDigest.ToLowerInvariant() `
        "--host" `
        "https://open-api-vst.bingx.pro" `
        "--execute" `
        "--plan-file" `
        $planItem.FullName `
        "--plan-digest" `
        $PlanDigest.ToLowerInvariant()

    $code = $LASTEXITCODE

    Write-Host "EXECUTE_ONCE_EXIT=$code"
    Write-Host "NO_AUTOMATIC_RETRY=YES"

    return
}

'''

    if operator.count(marker) != 1:
        raise PatchError("operator_help_marker_mismatch")

    operator = operator.replace(
        marker,
        execute_block + marker,
        1,
    )

    old_help = '''Write-Host ".\\tools\\operator.ps1 rehearse -Attempts 3"
Write-Host ""
Write-Host "This wrapper intentionally exposes no --execute action."'''

    new_help = '''Write-Host ".\\tools\\operator.ps1 rehearse -Attempts 3"
Write-Host ""
Write-Host "execute-once is VST-only, explicitly armed, and one-shot."
Write-Host "No automatic write retry is exposed by this wrapper."'''

    operator = replace_once(
        operator,
        old_help,
        new_help,
        "operator_help_block",
    )

    if "test_operator_execute_once_is_explicitly_armed_and_one_shot" in tests:
        raise PatchError("execute_once_test_already_exists")

    tests += r'''


def test_operator_execute_once_is_explicitly_armed_and_one_shot() -> None:
    root = Path(__file__).resolve().parents[3]

    operator = (
        root / "tools" / "operator.ps1"
    ).read_text(encoding="utf-8")

    tasks = (
        root / ".vscode" / "tasks.json"
    ).read_text(encoding="utf-8")

    block = operator.split(
        'if ($Action -eq "execute-once") {',
        1,
    )[1].split(
        'Write-Host "Alpha Pro VST operator"',
        1,
    )[0]

    assert "-ArmVstWrite" in operator
    assert '"scripts.bingx_vst_demo_order"' in block
    assert '"https://open-api-vst.bingx.pro"' in block
    assert '"--execute"' in block
    assert '"--plan-file"' in block
    assert '"--plan-digest"' in block
    assert "MAX_SUBMISSIONS=1" in block
    assert "AUTOMATIC_WRITE_RETRY=DISABLED" in block
    assert "NO_AUTOMATIC_RETRY=YES" in block
    assert block.count("& $Python") == 1
    assert block.count('"--execute"') == 1
    assert "execute-once" not in tasks
'''

    atomic_write(operator_path, operator, operator_newline)
    atomic_write(test_path, tests, tests_newline)

    print("PATCH=phase-1l-execute-once")
    print("ORDER_SUBMITTED=NO")
    print("EXECUTE_COMMAND_RUN=NO")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "recipe",
        choices=("phase-1l-execute-once",),
    )
    args = parser.parse_args()

    try:
        precheck()
        if args.recipe == "phase-1l-execute-once":
            phase_1l_execute_once()
    except PatchError as error:
        print(f"SAFE_PATCH=BLOCKED:{error}")
        return 2
    except Exception:
        print("SAFE_PATCH=FAILED:unexpected_error")
        return 1

    print("SAFE_PATCH=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
