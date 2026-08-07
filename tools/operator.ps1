param(
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

if ($Action -eq "execute-once") {
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

Write-Host "Alpha Pro VST operator"
Write-Host ""
Write-Host ".\tools\operator.ps1 watch"
Write-Host ".\tools\operator.ps1 watch -Attempts 3"
Write-Host ".\tools\operator.ps1 rehearse -Attempts 3"
Write-Host ""
Write-Host "execute-once is VST-only, explicitly armed, and one-shot."
Write-Host "No automatic write retry is exposed by this wrapper."
