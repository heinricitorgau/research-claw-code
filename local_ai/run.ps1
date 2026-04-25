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

function Write-Fail($message) {
    Write-Host "  xx $message" -ForegroundColor Red
    exit 1
}

function Write-Header($message) {
    Write-Host ""
    Write-Host "== $message ==" -ForegroundColor White
}

function Find-BinaryPath($primary, $fallbacks) {
    if (Test-Path $primary) {
        return $primary
    }
    foreach ($candidate in $fallbacks) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }
    return $null
}

function Test-Truthy($value) {
    if (-not $value) {
        return $false
    }
    return @("1", "true", "yes", "on") -contains $value.ToString().Trim().ToLowerInvariant()
}

function Resolve-CommandPath($name) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        return $null
    }
    return $command.Source
}

function Test-PortListening($port) {
    try {
        $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop
        return $listener.Count -gt 0
    } catch {
        return $false
    }
}

function Stop-ListenerOnPort($port, $label) {
    try {
        $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop
    } catch {
        return
    }
    if (-not $listeners) {
        return
    }
    Write-Warn "port $port already in use; restarting $label"
    $listeners | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
        try {
            Stop-Process -Id $_ -Force -ErrorAction Stop
        } catch {
        }
    }
    for ($i = 1; $i -le 10; $i++) {
        Start-Sleep -Seconds 1
        try {
            $remaining = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop
        } catch {
            $remaining = $null
        }
        if (-not $remaining) {
            Write-Ok "$label port $port cleared"
            return
        }
    }
    Write-Fail "could not free port $port for $label"
}

function Wait-HttpOk($url, $seconds) {
    for ($i = 1; $i -le $seconds; $i++) {
        try {
            Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 | Out-Null
            return $i
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    return $null
}

function Resolve-PythonPath($runtimeDir, $strictOffline) {
    $bundledPythonCandidates = @(
        (Join-Path $runtimeDir "python/python.exe"),
        (Join-Path $runtimeDir "python/python3.exe"),
        (Join-Path $runtimeDir "python/bin/python.exe"),
        (Join-Path $runtimeDir "bin/python.exe")
    )
    foreach ($candidate in $bundledPythonCandidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    if ($strictOffline) {
        return $null
    }

    $pythonPath = Resolve-CommandPath "python"
    if (-not $pythonPath) {
        $pythonPath = Resolve-CommandPath "python3"
    }
    if (-not $pythonPath) {
        $pythonPath = Resolve-CommandPath "py"
    }
    return $pythonPath
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
$runtimeDir = Join-Path $scriptDir "runtime"
$binDir = Join-Path $runtimeDir "bin"
$bundledOllamaHome = Join-Path $runtimeDir "ollama-home"
$manifestPath = Join-Path $runtimeDir "bundle-manifest.txt"

function Get-BundledModelManifestPath($bundledOllamaHome, $model) {
    $modelName = $model.Split(":", 2)[0]
    $baseDir = Join-Path $bundledOllamaHome ("models/manifests/registry.ollama.ai/library/" + $modelName)
    if ($model.Contains(":")) {
        $modelTag = $model.Split(":", 2)[1]
        $exactPath = Join-Path $baseDir $modelTag
        if (Test-Path $exactPath) {
            return $exactPath
        }
    }
    $latestPath = Join-Path $baseDir "latest"
    if (Test-Path $latestPath) {
        return $latestPath
    }
    if ($model.Contains(":")) {
        return (Join-Path $baseDir $model.Split(":", 2)[1])
    }
    return $latestPath
}

function Get-BundledModelRequestName($bundledOllamaHome, $model) {
    $modelName = $model.Split(":", 2)[0]
    $baseDir = Join-Path $bundledOllamaHome ("models/manifests/registry.ollama.ai/library/" + $modelName)
    if ($model.Contains(":")) {
        $modelTag = $model.Split(":", 2)[1]
        $exactPath = Join-Path $baseDir $modelTag
        if (Test-Path $exactPath) {
            return $model
        }
    }
    $latestPath = Join-Path $baseDir "latest"
    if (Test-Path $latestPath) {
        return $modelName
    }
    return $model
}

$defaultModel = "qwen2.5-coder:14b"
if (Test-Path $manifestPath) {
    $manifestModelLine = Select-String -Path $manifestPath -Pattern '^model=' -ErrorAction SilentlyContinue
    if ($manifestModelLine) {
        $defaultModel = $manifestModelLine.Line.Substring(6)
    }
}
$model = if ($env:CLAW_MODEL) { $env:CLAW_MODEL } else { $defaultModel }
$proxyPort = if ($env:CLAW_PROXY_PORT) { [int]$env:CLAW_PROXY_PORT } else { 8082 }
$ollamaPort = if ($env:CLAW_OLLAMA_PORT) { [int]$env:CLAW_OLLAMA_PORT } else { 11435 }
$ollamaUrl = if ($env:OLLAMA_URL) { $env:OLLAMA_URL } else { "http://127.0.0.1:$ollamaPort" }
$permissionMode = if ($env:CLAW_PERMISSION_MODE) { $env:CLAW_PERMISSION_MODE } else { "read-only" }
$systemPrompt = if ($env:CLAW_SYSTEM_PROMPT) { $env:CLAW_SYSTEM_PROMPT } else { "你是離線終端機助理。請全程只使用繁體中文回答，不要混用其他語言。不要自己切換語言，也不要詢問是否要改用別的語言。請直接在對話中輸出答案，不要主動建立、修改或輸出成檔案，除非使用者明確要求你這樣做。如果使用者要求寫程式，請直接給正確答案；如果沒有明確指定程式語言，預設輸出 C 語言程式；如果已指定語言，就照指定語言回答。如果題目很簡單，請直接提供最短、正確的 C 程式。若未指定格式，請用清楚、直接、適合終端機閱讀的方式回覆。" }
$strictOffline = Test-Truthy $env:CLAW_STRICT_OFFLINE

$proxyProcess = $null
$ollamaProcess = $null

try {
    Write-Host @"
   _____ _                    _       ___  ___
  / ____| |                  | |     / _ \|_ _|
 | |    | | __ ___      __   | |    | | | || |
 | |    | |/ _` \ \ /\ / /   | |    | |_| || |
 | |____| | (_| |\ V  V /    | |___ \___/|___|
  \_____|_|\__,_| \_/\_/     |_____| offline
"@
    Write-Host ""
    Write-Host "  model: $model" -ForegroundColor Cyan
    Write-Host "  perms: $permissionMode" -ForegroundColor Cyan
    Write-Host "  proxy: http://127.0.0.1:$proxyPort" -ForegroundColor Cyan
    Write-Host "  ollama: $ollamaUrl" -ForegroundColor Cyan
    if ($strictOffline) {
        Write-Host "  strict: on" -ForegroundColor Cyan
    }
    Write-Host ""

    Write-Header "preflight"
    $pythonPath = Resolve-PythonPath $runtimeDir $strictOffline
    if (-not $pythonPath) {
        if ($strictOffline) {
            Write-Fail "bundled Python not found; strict offline mode expects local_ai/runtime/python/python.exe"
        }
        Write-Fail "python not found; install Python or add it to PATH"
    }
    Write-Ok "python: $pythonPath"

    $clawFallbacks = @()
    if (-not $strictOffline) {
        $clawFallbacks = @(
            (Join-Path $projectDir "rust/target/release/claw.exe"),
            (Join-Path $projectDir "rust/target/debug/claw.exe"),
            (Resolve-CommandPath "claw")
        )
    }
    $clawPath = Find-BinaryPath (Join-Path $binDir "claw.exe") $clawFallbacks
    if (-not $clawPath) {
        if ($strictOffline) {
            Write-Fail "bundled claw.exe not found; strict offline mode expects local_ai/runtime/bin/claw.exe"
        }
        Write-Fail "cannot find claw binary"
    }
    Write-Ok "claw: $clawPath"

    $ollamaFallbacks = @()
    if (-not $strictOffline) {
        $ollamaFallbacks = @(
            (Resolve-CommandPath "ollama")
        )
    }
    $ollamaPath = Find-BinaryPath (Join-Path $binDir "ollama.exe") $ollamaFallbacks
    if (-not $ollamaPath) {
        if ($strictOffline) {
            Write-Fail "bundled ollama.exe not found; strict offline mode expects local_ai/runtime/bin/ollama.exe"
        }
        Write-Fail "cannot find ollama binary"
    }
    Write-Ok "ollama: $ollamaPath"

    if (Test-Path $bundledOllamaHome) {
        $env:OLLAMA_MODELS = Join-Path $bundledOllamaHome "models"
        Write-Ok "using bundled models: $env:OLLAMA_MODELS"
    } else {
        if ($strictOffline) {
            Write-Fail "bundled model cache not found; strict offline mode expects local_ai/runtime/ollama-home"
        }
        Write-Warn "bundled model cache not found; falling back to system ollama cache"
    }

    if (Test-Path $manifestPath) {
        $manifest = @{}
        Get-Content $manifestPath | ForEach-Object {
            if ($_ -match '^(.*?)=(.*)$') {
                $manifest[$matches[1]] = $matches[2]
            }
        }
        if ($manifest.ContainsKey("bundle_os") -and $manifest["bundle_os"] -ne "Windows") {
            Write-Fail "bundle targets $($manifest['bundle_os']), but this machine is Windows"
        }
        Write-Ok "bundle target matches this machine: Windows/$env:PROCESSOR_ARCHITECTURE"
    } elseif ($strictOffline) {
        Write-Fail "bundle manifest not found; strict offline mode expects local_ai/runtime/bundle-manifest.txt"
    }

    $env:OLLAMA_HOST = "127.0.0.1:$ollamaPort"
    $ollamaRequestModel = if (Test-Path $bundledOllamaHome) { Get-BundledModelRequestName $bundledOllamaHome $model } else { $model }

    Write-Header "ollama"
    if (Test-PortListening $ollamaPort) {
        Write-Ok "bundled service already running at $ollamaUrl"
    } else {
        Write-Info "starting bundled ollama service on $ollamaUrl"
        $ollamaProcess = Start-Process -FilePath $ollamaPath -ArgumentList "serve" -PassThru -WindowStyle Hidden
        $readyIn = Wait-HttpOk "$ollamaUrl/api/tags" 30
        if ($null -eq $readyIn) {
            Write-Fail "bundled ollama failed to start"
        }
        Write-Ok "bundled service ready in ${readyIn}s"
    }
    $bundledModelManifest = Get-BundledModelManifestPath $bundledOllamaHome $model
    if ((Test-Path $bundledOllamaHome) -and (-not (Test-Path $bundledModelManifest))) {
        Write-Fail "model '$model' is not available in the bundled runtime"
    }
    Write-Ok "model cached locally: $model"

    Write-Header "proxy"
    Stop-ListenerOnPort $proxyPort "proxy"
    $proxyLog = Join-Path ([System.IO.Path]::GetTempPath()) "claw-local-proxy.log"
    $proxyProcess = Start-Process -FilePath $pythonPath -ArgumentList @(
        (Join-Path $scriptDir "proxy.py"),
        "--model", $model,
        "--ollama-model", $ollamaRequestModel,
        "--port", "$proxyPort",
        "--ollama-url", $ollamaUrl,
        "--system-prompt", $systemPrompt
    ) -RedirectStandardOutput $proxyLog -RedirectStandardError $proxyLog -PassThru -WindowStyle Hidden
    $proxyReadyIn = Wait-HttpOk "http://127.0.0.1:$proxyPort/health" 10
    if ($null -eq $proxyReadyIn) {
        Write-Fail "proxy failed to start; check $proxyLog"
    }
    Write-Ok "proxy ready in ${proxyReadyIn}s"

    Write-Header "launch"
    Write-Host "ready local AI is up. Press Ctrl+C to exit." -ForegroundColor Green
    Write-Host ""

    $env:ANTHROPIC_BASE_URL = "http://127.0.0.1:$proxyPort"
    $env:ANTHROPIC_API_KEY = "local-ollama"

    $finalArgs = @()
    if ($args -notcontains "--model") {
        $finalArgs += @("--model", $model)
    }
    if (($args -notcontains "--permission-mode") -and (-not ($args | Where-Object { $_ -like "--permission-mode=*" }))) {
        $finalArgs += @("--permission-mode", $permissionMode)
    }
    $finalArgs += $args

    & $clawPath @finalArgs
    $exitCode = $LASTEXITCODE
    exit $exitCode
} finally {
    Write-Host ""
    Write-Host "[claw-local] shutting down..."
    if ($proxyProcess -and -not $proxyProcess.HasExited) {
        Stop-Process -Id $proxyProcess.Id -Force -ErrorAction SilentlyContinue
        Write-Info "proxy stopped"
    }
    if ($ollamaProcess -and -not $ollamaProcess.HasExited) {
        Stop-Process -Id $ollamaProcess.Id -Force -ErrorAction SilentlyContinue
        Write-Info "ollama stopped"
    }
}
