$ErrorActionPreference = "Stop"

function Write-Info($message) {
    Write-Host "  -> $message" -ForegroundColor Cyan
}

function Write-Ok($message) {
    Write-Host "  ok $message" -ForegroundColor Green
}

function Write-Fail($message) {
    Write-Host "  xx $message" -ForegroundColor Red
    exit 1
}

function Write-Header($message) {
    Write-Host ""
    Write-Host "== $message ==" -ForegroundColor White
}

function Resolve-CommandPath($name) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        return $null
    }
    return $command.Source
}

function Ensure-Directory($path) {
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path | Out-Null
    }
}

function Resolve-ModelManifestPath($model, $manifestRoot) {
    if ($model.Contains(":")) {
        $parts = $model.Split(":", 2)
        $exactPath = Join-Path $manifestRoot (Join-Path $parts[0] $parts[1])
        if (Test-Path $exactPath) {
            return $exactPath
        }
        $latestPath = Join-Path $manifestRoot (Join-Path $parts[0] "latest")
        if (Test-Path $latestPath) {
            return $latestPath
        }
        return $exactPath
    }
    $defaultPath = Join-Path $manifestRoot (Join-Path $model "latest")
    return $defaultPath
}

function Bundle-SingleModel($model, $manifestRoot, $blobRoot, $runtimeDir) {
    $sourceManifest = Resolve-ModelManifestPath $model $manifestRoot
    if (-not (Test-Path $sourceManifest)) {
        Write-Fail "cannot find manifest for model ${model}: $sourceManifest"
    }
    $manifestRelativePath = $sourceManifest.Substring($manifestRoot.Length + 1)

    $targetRoot = Join-Path $runtimeDir "ollama-home/models"
    $targetManifestPath = Join-Path $targetRoot ("manifests/registry.ollama.ai/library/" + $manifestRelativePath)
    $targetManifestDir = Split-Path $targetManifestPath -Parent
    $targetBlobDir = Join-Path $targetRoot "blobs"

    $ollamaHomeDir = Join-Path $runtimeDir "ollama-home"
    if (Test-Path $ollamaHomeDir) {
        Remove-Item -Path $ollamaHomeDir -Recurse -Force
    }

    Ensure-Directory $targetManifestDir
    Ensure-Directory $targetBlobDir
    Copy-Item -Path $sourceManifest -Destination $targetManifestPath -Force

    $manifestContent = Get-Content -Path $sourceManifest -Raw
    $matches = [regex]::Matches($manifestContent, 'sha256:[0-9a-f]{64}')
    foreach ($match in $matches) {
        $digest = $match.Value
        $blobName = $digest.Replace(":", "-")
        $blobPath = Join-Path $blobRoot $blobName
        if (-not (Test-Path $blobPath)) {
            Write-Fail "missing blob for digest $digest"
        }
        Copy-Item -Path $blobPath -Destination (Join-Path $targetBlobDir $blobName) -Force
    }
}

function Get-ModelManifestPath($model, $manifestRoot) {
    return (Resolve-ModelManifestPath $model $manifestRoot)
}

function Test-ModelCachedLocally($model, $manifestRoot) {
    return (Test-Path (Get-ModelManifestPath $model $manifestRoot))
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
$rustDir = Join-Path $projectDir "rust"
$runtimeDir = Join-Path $scriptDir "runtime"
$binDir = Join-Path $runtimeDir "bin"
$fastMode = $false
$cachedOnly = $false
$model = if ($env:CLAW_MODEL) { $env:CLAW_MODEL } else { "qwen2.5-coder:14b" }
foreach ($arg in $args) {
    switch ($arg) {
        "--fast" { $fastMode = $true; continue }
        "--cached-only" { $cachedOnly = $true; continue }
        "--help" {
            Write-Host "usage: powershell -ExecutionPolicy Bypass -File .\local_ai\prepare_bundle.ps1 [model] [--fast] [--cached-only]"
            Write-Host ""
            Write-Host "  --fast         優先重用既有 binary 與已打包模型，減少重建與重拷貝"
            Write-Host "  --cached-only  不下載模型；若本機快取缺少指定模型就直接失敗"
            exit 0
        }
        default {
            if ($arg.StartsWith("-")) {
                Write-Fail "unknown option: $arg"
            }
            $model = $arg
        }
    }
}
$sourceOllamaHome = if ($env:OLLAMA_HOME_OVERRIDE) { $env:OLLAMA_HOME_OVERRIDE } else { Join-Path $HOME ".ollama" }
$manifestRoot = Join-Path $sourceOllamaHome "models/manifests/registry.ollama.ai/library"
$blobRoot = Join-Path $sourceOllamaHome "models/blobs"

Write-Header "bundle target"
Ensure-Directory $binDir
Write-Ok "runtime dir: $runtimeDir"

Write-Header "tooling"
$cargoPath = Resolve-CommandPath "cargo"
if (-not $cargoPath) {
    Write-Fail "cargo not found; install Rust first"
}
$ollamaPath = Resolve-CommandPath "ollama"
if (-not $ollamaPath) {
    Write-Fail "ollama not found; install Ollama first"
}
Write-Ok "cargo: $(& $cargoPath --version)"
try {
    Write-Ok "ollama: $(& $ollamaPath --version)"
} catch {
    Write-Ok "ollama: installed"
}

Write-Header "build claw"
if ($fastMode -and (Test-Path (Join-Path $binDir "claw.exe"))) {
    Write-Ok "reusing bundled claw binary"
} elseif ($fastMode -and (Test-Path (Join-Path $rustDir "target/release/claw.exe"))) {
    Copy-Item -Path (Join-Path $rustDir "target/release/claw.exe") -Destination (Join-Path $binDir "claw.exe") -Force
    Write-Ok "reusing existing release claw binary"
} else {
    Push-Location $rustDir
    try {
        & $cargoPath build --workspace --release
    } finally {
        Pop-Location
    }
    $clawSource = Join-Path $rustDir "target/release/claw.exe"
    if (-not (Test-Path $clawSource)) {
        Write-Fail "cannot find built claw binary at $clawSource"
    }
    Copy-Item -Path $clawSource -Destination (Join-Path $binDir "claw.exe") -Force
    Write-Ok "bundled claw binary"
}

Write-Header "prepare model"
if (-not (Test-ModelCachedLocally $model $manifestRoot)) {
    if ($cachedOnly) {
        Write-Fail "model '$model' is not cached locally and --cached-only was requested"
    }
    Write-Info "model not cached yet, pulling $model"
    & $ollamaPath pull $model
}
if (-not (Test-ModelCachedLocally $model $manifestRoot)) {
    Write-Fail "model '$model' manifest is still missing after pull"
}
Write-Ok "model available locally: $model"

Write-Header "bundle ollama"
Copy-Item -Path $ollamaPath -Destination (Join-Path $binDir "ollama.exe") -Force
Write-Ok "bundled ollama executable"

if (-not (Test-Path $sourceOllamaHome)) {
    Write-Fail "cannot find Ollama home at $sourceOllamaHome"
}

if ($fastMode -and (Test-Path (Join-Path $runtimeDir "bundle-manifest.txt"))) {
    $existingModel = Select-String -Path (Join-Path $runtimeDir "bundle-manifest.txt") -Pattern '^model=' -ErrorAction SilentlyContinue
    if ($existingModel -and $existingModel.Line -eq "model=$model" -and (Test-Path (Join-Path $runtimeDir "ollama-home/models"))) {
        Write-Ok "reusing existing bundled model payload: $model"
    } else {
        Bundle-SingleModel $model $manifestRoot $blobRoot $runtimeDir
        Write-Ok "bundled only the selected model: $model"
    }
} else {
    Bundle-SingleModel $model $manifestRoot $blobRoot $runtimeDir
    Write-Ok "bundled only the selected model: $model"
}

Write-Header "write manifest"
$manifestLines = @(
    "prepared_at=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
    "bundle_os=Windows"
    "bundle_arch=$($env:PROCESSOR_ARCHITECTURE)"
    "model=$model"
    "fast_mode=$fastMode"
    "cached_only=$cachedOnly"
    "claw_binary=$(Join-Path $binDir 'claw.exe')"
    "ollama_binary=$(Join-Path $binDir 'ollama.exe')"
    "ollama_home=$(Join-Path $runtimeDir 'ollama-home')"
    "launch_command=powershell -ExecutionPolicy Bypass -File local_ai/run.ps1"
)
$manifestFilePath = Join-Path $runtimeDir "bundle-manifest.txt"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($manifestFilePath, $manifestLines, $utf8NoBom)
Write-Ok "bundle manifest written"

Write-Header "summary"
try {
    $sizeBytes = (Get-ChildItem -Path $runtimeDir -Recurse -Force | Measure-Object -Property Length -Sum).Sum
    if ($null -ne $sizeBytes) {
        Write-Info ("bundle size: {0:N2} MB" -f ($sizeBytes / 1MB))
    }
} catch {
}

Write-Host ""
Write-Host "離線 bundle 已完成。"
Write-Host ""
Write-Host "之後只要把整個 repo 複製到目標機器，就可以直接執行："
Write-Host "  powershell -ExecutionPolicy Bypass -File local_ai/run.ps1"
Write-Host ""
Write-Host "若想改模型："
Write-Host "  powershell -ExecutionPolicy Bypass -File local_ai/prepare_bundle.ps1 qwen2.5-coder:14b"
Write-Host ""
Write-Host "若想盡量少下載、少重建："
Write-Host "  powershell -ExecutionPolicy Bypass -File local_ai/prepare_bundle.ps1 --fast"
Write-Host ""
Write-Host "若只允許使用本機已快取的模型："
Write-Host "  powershell -ExecutionPolicy Bypass -File local_ai/prepare_bundle.ps1 --cached-only"
