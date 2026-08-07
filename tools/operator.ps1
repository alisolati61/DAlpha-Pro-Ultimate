param(
    [Parameter(Position = 0)]
    [ValidateSet("watch", "rehearse", "help")]
    [string]$Action = "help",

    [ValidateRange(1, 10)]
    [int]$Attempts = 1
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Watcher = Join-Path $Root "scripts\bingx_vst_watch_canary.py"

Set-Location $Root

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "STOP: virtualenv Python not found"
}

if ($Action -eq "watch") {
    Write-Host "READ-ONLY VST WATCH"
    Write-Host "HOST=https://open-api-vst.bingx.pro"
    Write-Host "ATTEMPTS=$Attempts"
    Write-Host "NO ORDER EXECUTION CAPABILITY"

    & $Python `
        $Watcher `
        "--host" `
        "https://open-api-vst.bingx.pro" `
        "--attempts" `
        "$Attempts"

    $code = $LASTEXITCODE

    Write-Host "WATCH_EXIT=$code"

    return
}

if ($Action -eq "rehearse") {
    Write-Host "SAFE VST REHEARSAL"
    Write-Host "HOST=https://open-api-vst.bingx.pro"
    Write-Host "ATTEMPTS=$Attempts"
    Write-Host "ORDER_SUBMISSION=DISABLED"

    & $Python `
        "-m" `
        "scripts.bingx_vst_rehearse" `
        "--host" `
        "https://open-api-vst.bingx.pro" `
        "--attempts" `
        "$Attempts"

    $code = $LASTEXITCODE

    Write-Host "REHEARSAL_EXIT=$code"

    return
}

Write-Host "Alpha Pro VST operator"
Write-Host ""
Write-Host ".\tools\operator.ps1 watch"
Write-Host ".\tools\operator.ps1 watch -Attempts 3"
Write-Host ".\tools\operator.ps1 rehearse -Attempts 3"
Write-Host ""
Write-Host "This wrapper intentionally exposes no --execute action."
