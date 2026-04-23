$ErrorActionPreference = "Stop"

function Write-Info($message) {
    Write-Host "  -> $message" -ForegroundColor Cyan
}

function Write-Ok($message) {
    Write-Host "  ok $message" -ForegroundColor Green
}

function Write-Warn($message) {
    Write-Host "  !! $message" -ForegroundColor Yellow
}

function Write-Header($message) {
    Write-Host ""
    Write-Host "== $message ==" -ForegroundColor White
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeDir = Join-Path $scriptDir "runtime"

Write-Header "cleanup target"
Write-Info "repo bundle dir: $runtimeDir"

if (-not (Test-Path $runtimeDir)) {
    Write-Warn "nothing to clean; $runtimeDir does not exist"
    exit 0
}

$bundleSize = "unknown"
try {
    $sizeBytes = (Get-ChildItem -Path $runtimeDir -Recurse -Force | Measure-Object -Property Length -Sum).Sum
    if ($null -ne $sizeBytes) {
        $bundleSize = "{0:N2} MB" -f ($sizeBytes / 1MB)
    }
} catch {
}

Remove-Item -Path $runtimeDir -Recurse -Force
Write-Ok "removed repo bundle: $runtimeDir"

Write-Host ""
Write-Host "已刪除由 local_ai/deploy_local.ps1 / local_ai/prepare_bundle.ps1 建立的 repo 內離線 bundle。"
Write-Host "釋放空間：約 $bundleSize"
Write-Host ""
Write-Host "注意："
Write-Host "- 這只會刪除 local_ai/runtime/"
Write-Host "- 不會刪除 `$env:USERPROFILE\.ollama 內原本或後續下載的系統全域模型快取"
