$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$startTime = Get-Date
try {
    & (Join-Path $scriptDir "prepare_bundle.ps1") @args
} finally {
    $elapsed = (Get-Date) - $startTime
    "`n總耗時：{0:D2}:{1:D2}:{2:D2}" -f $elapsed.Hours, $elapsed.Minutes, $elapsed.Seconds | Write-Host
}
