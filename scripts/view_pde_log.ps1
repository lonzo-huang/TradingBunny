param(
    [string]$LogFile,

    [string]$LogDir = "logs",

    [ValidateSet("all", "live", "sandbox")]
    [string]$Instance = "all",

    [ValidateSet("all", "fills", "orders", "pnl", "errors")]
    [string]$Preset = "all",

    [string[]]$Include = @(),

    [switch]$Follow
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ResolvedLogDir = Join-Path $RepoRoot $LogDir

function Resolve-TargetLogFile {
    param(
        [string]$InputLogFile,
        [string]$InputLogDir
    )

    if ($InputLogFile) {
        if (Test-Path $InputLogFile) {
            return (Resolve-Path $InputLogFile).Path
        }

        $candidate = Join-Path $InputLogDir $InputLogFile
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }

        throw "Log file not found: $InputLogFile"
    }

    if (-not (Test-Path $InputLogDir)) {
        throw "Log directory not found: $InputLogDir"
    }

    $latest = Get-ChildItem -Path $InputLogDir -Filter "*.log" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if (-not $latest) {
        throw "No .log files found in: $InputLogDir"
    }

    return $latest.FullName
}

function Build-Pattern {
    param(
        [string]$InputInstance,
        [string]$InputPreset,
        [string[]]$InputInclude
    )

    $instancePattern = switch ($InputInstance) {
        "live"    { "POLYMARKET-001" }
        "sandbox" { "POLYMARKET-SBX" }
        default    { "." }
    }

    $presetPatterns = switch ($InputPreset) {
        "fills"  { @("OrderFilled", "PositionOpened", "position_closed", "PHASE_B_SETTLE") }
        "orders" { @("OrderInitialized", "order_submitted", "OrderAccepted", "OrderDenied", "Cannot submit market order") }
        "pnl"    { @("\[PNL\]", "PHASE_B_SETTLE", "realized_pnl", "Round PnL", "Total:") }
        "errors" { @("\[ERROR\]", "\[WARN\]", "OrderDenied", "Cannot submit market order", "Traceback") }
        default   { @(".") }
    }

    $parts = @()
    $parts += "(?=.*$instancePattern)"

    foreach ($p in $presetPatterns) {
        if ($p -ne ".") {
            $parts += "(?=.*$p)"
        }
    }

    foreach ($extra in $InputInclude) {
        if (-not [string]::IsNullOrWhiteSpace($extra)) {
            $escaped = [regex]::Escape($extra.Trim())
            $parts += "(?=.*$escaped)"
        }
    }

    return ($parts -join "")
}

$targetLog = Resolve-TargetLogFile -InputLogFile $LogFile -InputLogDir $ResolvedLogDir
$pattern = Build-Pattern -InputInstance $Instance -InputPreset $Preset -InputInclude $Include

Write-Host "[LOG]     $targetLog"
Write-Host "[FILTER]  instance=$Instance preset=$Preset include=$($Include -join ',')"

$stream = if ($Follow) {
    Get-Content -Path $targetLog -Wait
} else {
    Get-Content -Path $targetLog
}

$stream | Where-Object { $_ -match $pattern }
