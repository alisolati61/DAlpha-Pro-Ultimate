param(
    [Parameter(Position = 0)]
    [ValidateSet(
        "status",
        "focused",
        "vst",
        "full",
        "quality",
        "verify",
        "release",
        "help"
    )]
    [string]$Action = "help"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

Set-Location $Root

function Require-Python {
    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
        throw "STOP: virtualenv Python not found: $Python"
    }
}

function Run-Native {
    param(
        [string]$Name,
        [string]$File,
        [string[]]$Arguments = @()
    )

    Write-Host ""
    Write-Host "=== $Name ==="

    & $File @Arguments
    $code = $LASTEXITCODE

    if ($code -ne 0) {
        throw "STOP: $Name failed with exit code $code"
    }
}

function New-TestTemp {
    param([string]$Name)

    return Join-Path `
        ([System.IO.Path]::GetTempPath()) `
        "alpha-pro-$Name-$([guid]::NewGuid().ToString('N'))"
}

function Show-Status {
    $branch = (git branch --show-current).Trim()
    $sha = (git rev-parse --short HEAD).Trim()
    $dirty = @(git status --porcelain)

    Write-Host "BRANCH=$branch"
    Write-Host "HEAD=$sha"

    if ($dirty.Count -eq 0) {
        Write-Host "WORKTREE=CLEAN"
    }
    else {
        Write-Host "WORKTREE=MODIFIED"
        git status --short
    }
}

function Run-Focused {
    Require-Python

    $temp = New-TestTemp "focused"
    New-Item -ItemType Directory -Force -Path $temp | Out-Null

    Run-Native `
        "FOCUSED TESTS" `
        $Python `
        @(
            "-m", "pytest",
            "-p", "no:cacheprovider",
            "--basetemp=$temp",
            "tests/unit/vst_runtime/test_canary_capture.py",
            "tests/unit/vst_runtime/test_canary_watch_cli.py"
        )
}

function Run-Vst {
    Require-Python

    $temp = New-TestTemp "vst"
    New-Item -ItemType Directory -Force -Path $temp | Out-Null

    Run-Native `
        "VST RUNTIME TESTS" `
        $Python `
        @(
            "-m", "pytest",
            "-p", "no:cacheprovider",
            "--basetemp=$temp",
            "tests/unit/vst_runtime"
        )
}

function Run-Full {
    Require-Python

    $temp = New-TestTemp "full"
    New-Item -ItemType Directory -Force -Path $temp | Out-Null

    Run-Native `
        "FULL PYTEST" `
        $Python `
        @(
            "-m", "pytest",
            "-p", "no:cacheprovider",
            "--basetemp=$temp"
        )
}

function Run-Quality {
    Require-Python

    Run-Native `
        "TARGETED RUFF" `
        $Python `
        @(
            "-m", "ruff", "check",
            "scripts/bingx_vst_watch_canary.py",
            "src/vst_runtime/canary_capture.py",
            "tests/unit/vst_runtime/test_canary_capture.py",
            "tests/unit/vst_runtime/test_canary_watch_cli.py"
        )

    Run-Native `
        "TARGETED MYPY" `
        $Python `
        @(
            "-m", "mypy",
            "--follow-imports=skip",
            "src/vst_runtime/canary_capture.py"
        )

    Run-Native `
        "COMPILEALL" `
        $Python `
        @(
            "-m", "compileall", "-q",
            "src",
            "scripts"
        )

    Run-Native `
        "DIFF CHECK" `
        "git" `
        @("diff", "HEAD", "--check")
}

switch ($Action) {
    "status" {
        Show-Status
    }

    "focused" {
        Run-Focused
    }

    "vst" {
        Run-Vst
    }

    "full" {
        Run-Full
    }

    "quality" {
        Run-Quality
    }

    "verify" {
        Show-Status
        Run-Focused
        Run-Vst
        Run-Quality

        Write-Host ""
        Write-Host "=============================="
        Write-Host "VERIFY=PASS"
        Write-Host "=============================="
    }

    "release" {
        Show-Status
        Run-Focused
        Run-Vst
        Run-Full
        Run-Quality

        Write-Host ""
        Write-Host "=============================="
        Write-Host "RELEASE_VERIFY=PASS"
        Write-Host "=============================="
    }

    "help" {
        Write-Host "Alpha Pro development toolkit"
        Write-Host ""
        Write-Host ".\tools\dev.ps1 status"
        Write-Host ".\tools\dev.ps1 focused"
        Write-Host ".\tools\dev.ps1 vst"
        Write-Host ".\tools\dev.ps1 full"
        Write-Host ".\tools\dev.ps1 quality"
        Write-Host ".\tools\dev.ps1 verify"
        Write-Host ".\tools\dev.ps1 release"
    }
}
