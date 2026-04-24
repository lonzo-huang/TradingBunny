param(
    [ValidateSet("sandbox", "live", "both")]
    [string]$Mode = "both",

    [string]$LogDir = "logs",

    [string]$Tag = "pde"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ResolvedLogDir = Join-Path $RepoRoot $LogDir

if (-not (Test-Path $ResolvedLogDir)) {
    New-Item -ItemType Directory -Path $ResolvedLogDir | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logName = "{0}_{1}_{2}.log" -f $Tag, $Mode, $timestamp
$logPath = Join-Path $ResolvedLogDir $logName

Write-Host "[START] Mode=$Mode"
Write-Host "[LOG]   $logPath"
Write-Host "[INFO]  Press Ctrl+C to stop"

$runner = Join-Path $RepoRoot "live\run_polymarket_pde.py"

if (-not (Test-Path $runner)) {
    throw "Runner not found: $runner"
}

Push-Location $RepoRoot
try {
    python $runner --mode $Mode *>&1 | Tee-Object -FilePath $logPath
}
finally {
    Pop-Location
}
