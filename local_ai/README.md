# claw 本地離線 AI

這套流程的目標不是「在目標機器上現場安裝一堆東西」，而是做出真正可搬運的 bundle：

1. 在有網路的機器上先把 `claw`、`ollama`、模型快取打包進 repo
2. 之後把整個 `research-claw-code` 資料夾複製到另一台機器
3. 在離線環境直接執行 `bash local_ai/run.sh`

這樣才符合「下載資料夾後，下個指令就能直接跑，而且不需要網路」。

目前離線流程會用到的入口腳本也都集中在 `local_ai/` 目錄下。

現在的 launcher 不依賴系統安裝的 `ollama`。它會直接使用 `local_ai/runtime/` 內打包好的執行檔與模型，並透過系統自帶的 Python 3 跑一層很薄的本地 proxy。離線模式下，proxy 會預設附加繁體中文 system prompt，因此一般提問會直接用中文回覆；如果要它寫程式而你沒有指定語言，預設會輸出 `C` 語言。啟動時也會預設使用 `read-only` 權限，所以它會直接輸出答案，而不是主動改檔或寫檔。

## 你要用的兩個指令

### 第一次準備 bundle

```bash
cd ~/Desktop/research-claw-code
bash local_ai/deploy_local.sh
```

Windows PowerShell：

```powershell
Set-Location ~/Desktop/research-claw-code
powershell -ExecutionPolicy Bypass -File .\local_ai\deploy_local.ps1
```

等價於：

```bash
bash local_ai/prepare_bundle.sh
```

預設模型是 `qwen2.5-coder:14b`。若想指定別的模型：

```bash
bash local_ai/prepare_bundle.sh qwen2.5-coder:14b
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\prepare_bundle.ps1 qwen2.5-coder:14b
```

### 之後離線啟動

```bash
cd ~/Desktop/research-claw-code
bash local_ai/run.sh
```

Windows PowerShell：

```powershell
Set-Location ~/Desktop/research-claw-code
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
```

也可以直接丟 prompt：

```bash
bash local_ai/run.sh "幫我解釋這個 repo 的架構"
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1 "幫我解釋這個 repo 的架構"
```

### 用完後清理 bundle

```bash
bash local_ai/cleanup_local.sh
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\cleanup_local.ps1
```

這會刪除 `local_ai/runtime/` 內的 bundled `claw`、bundled `ollama`、模型快取與 manifest。

## 產物會放哪裡

執行 `prepare_bundle.sh` 後，會產生：

```text
local_ai/runtime/
├── bin/
│   ├── claw
│   └── ollama
├── ollama-home/
└── bundle-manifest.txt
```

其中：

- `bin/claw` 是可直接執行的 CLI
- `bin/ollama` 是直接打包進 repo 的本地模型引擎
- `ollama-home/` 是模型與 manifest 快取

## 目前架構

```text
你
  ↓
claw
  ↓ Anthropic Messages API
local_ai/proxy.py
  ↓ OpenAI Chat Completions
bundled Ollama
  ↓
bundled local model
```

## 注意事項

- `prepare_bundle.sh` 需要網路，因為它可能要拉模型與做 release build。
- `run.sh` 是離線優先，不會主動幫你下載任何東西。
- `local_ai/runtime/` 可能很大，因為模型本身會一起被打包。
- 如果你用完後想回收 repo 內空間，可以執行 `bash local_ai/cleanup_local.sh`。
- 如果你要把它分發給別人，直接壓縮整個 `research-claw-code` 資料夾即可。
- 目前這個 bundle 是針對「相同作業系統 + 相同 CPU 架構」攜帶。例：這次打的是 `macOS arm64`，所以最穩是搬到另一台 `macOS arm64` 機器。`run.sh` 會檢查這個條件。
- 也就是說：不需要安裝第三方軟體，但不能保證同一份 bundle 同時跨 `macOS / Linux / Windows` 或 `arm64 / x86_64` 全部通用。
- 在 macOS 上，launcher 會優先使用系統自帶的 `/usr/bin/python3`，所以目標機器不需要另外安裝 Python。
- 在 Windows 上，PowerShell launcher 會優先尋找 `python`、`python3` 或 `py`。
- `bash local_ai/cleanup_local.sh` 不會動到 `~/.ollama` 的全域模型快取，避免誤刪你原本就有的模型。
- `powershell -ExecutionPolicy Bypass -File .\local_ai\cleanup_local.ps1` 也只會清 repo 內的 bundle。

## 常用環境變數

```bash
CLAW_MODEL=qwen2.5-coder:14b bash local_ai/run.sh
CLAW_OLLAMA_PORT=11435 bash local_ai/run.sh
CLAW_PERMISSION_MODE=read-only bash local_ai/run.sh
CLAW_SYSTEM_PROMPT="請全程使用繁體中文，並用條列整理答案。" bash local_ai/run.sh
```

Windows PowerShell：

```powershell
$env:CLAW_MODEL="qwen2.5-coder:14b"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_OLLAMA_PORT="11435"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_PERMISSION_MODE="read-only"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_SYSTEM_PROMPT="請全程使用繁體中文，並用條列整理答案。"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
```

## 疑難排解

### 找不到 bundle

代表還沒先執行：

```bash
bash local_ai/deploy_local.sh
```

### 想確認 bundle 內容

```bash
cat local_ai/runtime/bundle-manifest.txt
```

### 查看執行日誌

```bash
tail -f /tmp/claw-local-ollama.log
tail -f /tmp/claw-local-proxy.log
```
