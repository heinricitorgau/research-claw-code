# research-claw-code

這個 repository 主要有兩條使用路線：

1. 離線 bundle 路線：先在有網路的電腦打包 `claw + ollama + model`，之後把整個資料夾搬到無網路環境直接跑。
2. Rust CLI 路線：在 `rust/` 內直接開發、建置、測試 `claw` CLI。

如果你現在的目標是「下載資料夾後，離線直接問問題」，請先看下面的離線 bundle 流程。

## 離線 bundle 快速開始

### 1. 在有網路的機器準備 bundle

macOS / Linux:

```bash
cd ~/Desktop/research-claw-code
bash deploy_local.sh
```

Windows PowerShell：

```powershell
Set-Location ~/Desktop/research-claw-code
powershell -ExecutionPolicy Bypass -File .\deploy_local.ps1
```

這一步會：

- 建置 `claw` CLI
- 打包 bundled `ollama`
- 下載並封裝指定模型
- 產生 `local_ai/runtime/` 離線執行環境

預設模型是 `qwen2.5-coder:14b`。

若想指定模型：

macOS / Linux:

```bash
bash local_ai/prepare_bundle.sh qwen2.5-coder:14b
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\prepare_bundle.ps1 qwen2.5-coder:14b
```

若想盡量少下載、少重建：

```bash
bash local_ai/prepare_bundle.sh --fast
```

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\prepare_bundle.ps1 --fast
```

若只允許使用本機已快取模型，不接受現場下載：

```bash
bash local_ai/prepare_bundle.sh --cached-only
```

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\prepare_bundle.ps1 --cached-only
```

### 2. 把整個資料夾搬到目標機器

把整個 `research-claw-code/` 連同 `local_ai/runtime/` 一起複製過去即可。

### 3. 在離線環境直接啟動

macOS / Linux:

```bash
cd ~/Desktop/research-claw-code
bash local_ai/run.sh
```

Windows PowerShell：

```powershell
Set-Location ~/Desktop/research-claw-code
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
```

也可以直接丟一次性問句：

```bash
bash local_ai/run.sh --output-format text prompt "幫我整理這份會議紀錄"
```

```bash
bash local_ai/run.sh "請用中文解釋這個錯誤訊息"
```

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1 --output-format text prompt "幫我整理這份會議紀錄"
```

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1 "請用中文解釋這個錯誤訊息"
```

## 離線模式的預設行為

- 預設以繁體中文回覆，錯誤訊息也會以繁中 UTF-8 直接回傳（不會被跳脫成 `\uXXXX`）
- 若要求寫程式但未指定語言，預設輸出 `C` 語言程式
- 預設以 `read-only` 權限啟動，所以會直接輸出答案，不會主動寫檔
- 對 C 程式題，proxy 會先做本地語法與基本結構檢查；若明顯不是 C 或無法編譯，會要求模型重寫，最多重試兩次
- 一般問題走真正的 SSE 串流，token 會逐步顯示；C 題修復流程因為需要完整文字才能做語法檢查，會等模型產生完畢再一次輸出
- 多行輸入建議用 `/multiline`
- `Shift+Enter` 與 `Ctrl+J` 可用於插入換行，但 `Shift+Enter` 是否生效仍取決於終端機

如果你要輸入多行內容，建議這樣用：

```text
/multiline
第一行
第二行
/submit
```

Windows 上尤其建議把 `/multiline` 當主要方案。

## 清理 bundle

macOS / Linux:

```bash
bash cleanup_local.sh
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\cleanup_local.ps1
```

這只會刪除 repo 內的 `local_ai/runtime/`，不會動到 `~/.ollama` 的全域模型快取。

## 常用環境變數

```bash
CLAW_MODEL=qwen2.5-coder:14b bash local_ai/run.sh
CLAW_OLLAMA_PORT=11435 bash local_ai/run.sh
CLAW_PROXY_PORT=8082 bash local_ai/run.sh
CLAW_PERMISSION_MODE=read-only bash local_ai/run.sh
CLAW_SYSTEM_PROMPT="請全程使用繁體中文，回答精簡一點" bash local_ai/run.sh
```

```powershell
$env:CLAW_MODEL="qwen2.5-coder:14b"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_OLLAMA_PORT="11435"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_PROXY_PORT="8082"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_PERMISSION_MODE="read-only"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_SYSTEM_PROMPT="請全程使用繁體中文，回答精簡一點"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
```

## 注意事項

- bundle 目前是「相同作業系統 + 相同 CPU 架構」可攜
- `prepare_bundle.sh` / `prepare_bundle.ps1` 需要在有網路的環境執行
- `--fast` 會優先重用既有 binary 與已打包模型，減少重建與重拷貝
- `--cached-only` 不會下載模型；若本機沒有快取指定模型就會直接失敗
- `local_ai/runtime/` 可能很大，因為模型本身會一起打包
- bundle manifest 在 Windows 上也是以 BOM-less UTF-8 寫入，搬到 macOS / Linux 的 `run.sh` 讀取不會卡在 BOM
- 重新啟動時若舊 proxy/ollama 還占著 port，Windows 與 macOS / Linux 都會等最多 10 秒嘗試釋放 port 再接手
- macOS launcher 會優先使用系統自帶的 `/usr/bin/python3`
- Windows launcher 會優先尋找 `python`、`python3` 或 `py`
- `deploy_local.sh` 與 `deploy_local.ps1` 都會在結束時印出總耗時
- 若主要用途是解 C 題，建議優先用 `qwen2.5-coder:14b`；機器較吃緊時再考慮 `qwen2.5-coder:7b`

## 專案結構

```text
.
├── local_ai/   # 離線 bundle、proxy、啟動腳本
├── rust/       # claw CLI 主實作
├── src/        # 早期 Python port / 研究與對照工具
├── tests/      # Python 端測試與加固驗證
└── docs/       # 補充研究文件
```

## 文件導覽

- `usage.txt`: 最短版離線使用說明
- `USAGE.md`: `claw` CLI 與 Rust workspace 用法
- `local_ai/README.md`: 離線 bundle 的細節說明
- `rust/README.md`: Rust workspace、crate 分工與開發入口
