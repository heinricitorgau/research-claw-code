# research-claw-code 離線 AI 增強實施報告

## 1. 實施狀態

✅ **全部功能已實現** - 所有四層增強都已完整集成到現有架構中。

---

## 2. 文件更改清單

### 核心增強層（已完成）

| 文件/目錄 | 狀態 | 說明 |
|-----------|------|------|
| `local_ai/prompts/default_zh_tw.md` | ✅ | 預設繁體中文提示策略 |
| `local_ai/prompts/c_programming.md` | ✅ | C 程式題專用提示 |
| `local_ai/prompts/project_assistant.md` | ✅ | 專案助理提示 |
| `local_ai/prompt_loader.py` | ✅ | 提示動態載入、環境變數支持 |
| `local_ai/checkers/check_c_answer.py` | ✅ | C 答案檢查器（#include、main、編譯、測試、安全） |
| `local_ai/checkers/check_markdown_answer.py` | ✅ | Markdown 答案檢查器 |
| `local_ai/checkers/check_offline_safety.py` | ✅ | 離線安全檢查（pip、npm、curl 等） |
| `local_ai/repair_loop.py` | ✅ | 自動修正循環（修復提示、重試邏輯） |
| `local_ai/rag/build_index.py` | ✅ | 本機 RAG 索引建構（keyword / BM25 scoring） |
| `local_ai/rag/search_docs.py` | ✅ | 本機 RAG 搜尋（頂-K 結果、內容格式化） |
| `local_ai/rag/import_usb_docs.py` | ✅ | USB 文檔導入工具 |
| `local_ai/proxy.py` | ✅ | 完整整合（提示、檢查、RAG、修正循環） |

### 運行時腳本（已完成）

| 文件 | 狀態 | 功能 |
|------|------|------|
| `local_ai/run.sh` | ✅ | `--rag`、`--import-docs`、`--reindex-rag` 參數 |
| `local_ai/run.ps1` | ✅ | `--rag`、`--import-docs`、`--reindex-rag` 參數 |

### 文檔（已完成）

| 文件 | 狀態 | 內容 |
|------|------|------|
| `local_ai/README.md` | ✅ | 提示設定、本機檢查器、RAG、USB 工作流、環境變數 |
| `README.md` | ✅ | Level 1 離線部署、四層功能簡介 |

### 測試（已完成）

| 文件 | 狀態 | 涵蓋內容 |
|------|------|---------|
| `tests/local_ai/test_prompt_profile.py` | ✅ | 提示載入、環境變數、fallback |
| `tests/local_ai/test_c_checker.py` | ✅ | 檢查規則、C++ 檢測、編譯驗證 |
| `tests/local_ai/test_rag_search.py` | ✅ | 索引建構、搜尋、內容格式化 |
| `tests/local_ai/test_repair_loop.py` | ✅ | 修復邏輯、重試、環境變數 |
| `tests/local_ai/test_offline_commands.py` | ✅ | 無網路驗證、命令安全性 |

---

## 3. 新 CLI 命令

### 提示設定

```bash
# 使用 C 程式提示
CLAW_PROMPT_PROFILE=c_programming bash local_ai/run.sh

# 使用專案助理提示
CLAW_PROMPT_PROFILE=project_assistant bash local_ai/run.sh

# 使用自訂系統提示
CLAW_SYSTEM_PROMPT="只使用簡體中文。" bash local_ai/run.sh
```

### RAG 文檔庫

```bash
# 導入 USB 文檔
bash local_ai/run.sh --import-docs /Volumes/USB/my_notes

# 重新建立 RAG 索引
bash local_ai/run.sh --reindex-rag

# 帶 RAG 提問
bash local_ai/run.sh --rag "根據我的 C 語言筆記解釋 pointer"
```

### 自動修正

```bash
# 調整最大重試次數
CLAW_MAX_REPAIR_RETRIES=3 bash local_ai/run.sh

# 預設 2 次重試（若本機 C 檢查器失敗）
bash local_ai/run.sh
```

### Windows PowerShell

```powershell
$env:CLAW_PROMPT_PROFILE="c_programming"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1

powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1 --import-docs E:\my_notes
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1 --rag "請解釋 array"

$env:CLAW_MAX_REPAIR_RETRIES="3"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
```

---

## 4. 離線測試方式

### 4.1 快速驗證四層功能

```bash
# 測試提示層
python3 tests/local_ai/test_prompt_profile.py

# 測試檢查層
python3 tests/local_ai/test_c_checker.py

# 測試 RAG 層
python3 tests/local_ai/test_rag_search.py

# 測試修正循環
python3 tests/local_ai/test_repair_loop.py

# 驗證無網路
python3 tests/local_ai/test_offline_commands.py
```

### 4.2 完整離線流程測試

```bash
# 1. 準備 bundle（需要網路，一次性）
bash local_ai/deploy_local.sh

# 2. 模擬創建 USB 文檔
mkdir -p local_ai/rag/docs
echo "# C 筆記
## Pointers
指標是變數的記憶體位址。" > local_ai/rag/docs/c_notes.md

# 3. 重建索引（離線）
bash local_ai/run.sh --reindex-rag

# 4. 帶 RAG 提問（離線，需要 Ollama 模型）
bash local_ai/run.sh --rag "pointer 是什麼？"

# 5. 直接提問 C 題（會自動檢查和修正）
bash local_ai/run.sh "寫一個 C 程式計算階乘"
```

### 4.3 Windows 離線驗收（Level 1 air-gap）

```powershell
# 1. 準備 bundle（在有網路的 Windows）
powershell -ExecutionPolicy Bypass -File .\local_ai\deploy_local.ps1

# 2. 複製整個資料夾到 USB

# 3. 在離線 Windows 上驗收
$env:CLAW_STRICT_OFFLINE="1"
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1 "寫一個 C 程式"

# 嚴格模式會拒絕任何系統 binary，只用 bundle
```

### 4.4 檢查器輸出驗證

```bash
# 直接測試 C 檢查器
echo '#include <stdio.h>
int main() { printf("hi\n"); return 0; }' > /tmp/test.c

python3 local_ai/checkers/check_c_answer.py /tmp/test.c

# 應輸出 JSON:
# {
#   "ok": false,
#   "score": 0.55,
#   "issues": ["Missing test input/output"],
#   "suggestions": ["Add at least one sample run"]
# }
```

### 4.5 RAG 功能驗證

```bash
# 建立測試文檔
mkdir -p local_ai/rag/docs
cat > local_ai/rag/docs/test.md << 'EOF'
# Arrays in C
## Definition
An array is a collection of elements.

## Usage
int arr[10];
EOF

# 建立索引
python3 local_ai/rag/build_index.py

# 搜尋
python3 -c "
import sys
sys.path.insert(0, 'local_ai')
from rag.search_docs import search
results = search('array')
for r in results:
    print(f'{r[\"source\"]}: {r[\"heading\"]}')
"
```

---

## 5. 已知限制

### 5.1 環境依賴

| 限制 | 說明 | 解決方案 |
|------|------|---------|
| 必須有 Python 3.7+ | proxy.py 需要 Python | Windows 需加入 portable Python；macOS 自帶 Python3 |
| 可選 C 編譯器 | 本機編譯檢查需要 gcc/clang/cc | 缺時僅做靜態檢查，跳過編譯驗證 |
| RAG 搜尋無向量化 | 使用關鍵字 + BM25，不如向量相似度精確 | 針對程式代碼和簡短文本足夠；大型知識庫建議事後向量化 |

### 5.2 功能限制

| 限制 | 說明 |
|------|------|
| 模型固定在 bundle 內 | 建置後無法更換模型；需重新 prepare_bundle |
| 每個 bundle 特定於 OS/架構 | macOS arm64 bundle 不能搬到 Windows；需重新打包 |
| C 修復最多 2 次 | 設計用於快速修復，不適合複雜多輪演化 |
| 離線模式無法新增套件 | pip / npm / cargo 會被檢查器拒絕 |

### 5.3 平台特異性

| 平台 | 支援狀態 | 備註 |
|------|---------|------|
| macOS arm64 | ✅ 完整 | 自帶 Python3，可用嚴格離線模式 |
| macOS x86_64 | ✅ 完整 | 同上 |
| Linux (glibc) | ✅ 完整 | 需要系統 Python3 或 bundled Python |
| Windows PowerShell | ✅ 完整 | 支援 CLAW_STRICT_OFFLINE；推薦 portable Python |
| Windows bash (WSL/Git Bash) | ⚠️ 部分 | 可運行但未測試完整 Level 1 air-gap |

---

## 6. 已知問題和應急處理

### 6.1 檢查器總是警告

**症狀**：即使 C 代碼看似正確，仍有 issue。

**原因**：
- 缺少本機編譯器 → 跳過編譯檢查
- 缺少測試輸入/輸出標記

**應急**：
```bash
# 檢查是否有編譯器
which gcc clang cc

# 手動安裝（仅在有網路的準備機）
apt install build-essential   # Ubuntu/Debian
brew install gcc             # macOS
```

### 6.2 RAG 搜尋找不到文檔

**症狀**：`--rag` 問題沒有回傳相關內容。

**原因**：
- 文件副檔名不在支援清單
- 索引未建立或過期

**應急**：
```bash
# 檢查支援的副檔名
python3 -c "import sys; sys.path.insert(0, 'local_ai'); from rag.build_index import ALLOWED_SUFFIXES; print(ALLOWED_SUFFIXES)"

# 強制重建索引
bash local_ai/run.sh --reindex-rag
```

### 6.3 修復循環無法改進

**症狀**：C 題經過 2 次重試仍未通過，仍輸出警告。

**原因**：
- 模型生成質量不足
- 問題本身超出模型能力

**應急**：
```bash
# 嘗試增加重試次數
CLAW_MAX_REPAIR_RETRIES=4 bash local_ai/run.sh

# 嘗試更強的模型（需重新 prepare_bundle）
bash local_ai/prepare_bundle.sh qwen2.5-coder:32b

# 使用 RAG 提供額外上下文
bash local_ai/run.sh --rag "寫一個 C 程式計算階乘"
```

---

## 7. 建議的下一步改進

### 優先級 1：核心增強（3-5 週）

- [ ] **bundled proxy.exe** - 消除 Windows 對系統 Python 的依賴，達成完全 Level 1
- [ ] **向量 RAG 選項** - 可選的輕量級向量索引（如 annoy），用於大型文檔庫
- [ ] **擴展檢查器** - 新增 Python / JavaScript 檢查器，遵循 C 檢查器設計

### 優先級 2：使用體驗（2-3 週）

- [ ] **REPL 模式強化** - 在 proxy 中維持多輪對話狀態，改進 C 題迭代
- [ ] **TUI 增強** - 在 claw CLI 中直接顯示 RAG 搜尋結果和檢查器警告
- [ ] **批量導入工具** - 支援從 ZIP / ISO 自動導入文檔

### 優先級 3：相容性（1-2 週）

- [ ] **跨架構 bundle** - 通用 Linux x86_64 bundle（使用 AppImage / FlatPak）
- [ ] **模型預設清單** - 通用推薦模型，依硬體自動選擇
- [ ] **bundle 版本管理** - 同步 claw 與 proxy 版本，避免不相容

### 優先級 4：生產強化（2-4 週）

- [ ] **離線分析工具** - 代碼結構分析、編譯錯誤本地修復
- [ ] **本機知識庫** - 在 `local_ai/reference_data/` 中內建 C/POSIX 標準庫文檔
- [ ] **效能優化** - cache BM25 分數、parallelized 搜尋、lazy index loading
- [ ] **故障恢復** - 自動 bundle 完整性驗證、損毀索引修復

---

## 8. 檔案大小估計

```
local_ai/runtime/
├── bin/
│   ├── claw (~30-50 MB)
│   └── ollama (~50-100 MB)
├── ollama-home/
│   └── models/
│       └── (model cache, 7B-34B: 5-20 GB)
└── python/ (optional, Windows only: ~100-150 MB)

Total: 5-21 GB (depends on model size)
```

對於 USB 配置：
- 8GB USB：只能裝 7B 模型
- 32GB USB：可裝 14B-20B 模型  
- 64GB USB：可裝 32B 模型

---

## 9. 支援矩陣

| 功能 | macOS arm64 | macOS x86 | Linux x64 | Windows x64 |
|------|-----------|----------|----------|-----------|
| Prompt profiles | ✅ | ✅ | ✅ | ✅ |
| C checker | ✅ | ✅ | ✅ | ✅ |
| Markdown checker | ✅ | ✅ | ✅ | ✅ |
| Offline safety | ✅ | ✅ | ✅ | ✅ |
| Repair loop | ✅ | ✅ | ✅ | ✅ |
| RAG indexing | ✅ | ✅ | ✅ | ✅ |
| RAG search | ✅ | ✅ | ✅ | ✅ |
| USB import | ✅ | ✅ | ✅ | ✅ |
| CLAW_STRICT_OFFLINE | ⚠️ | ⚠️ | ⚠️ | ✅ |

---

## 10. 驗收清單

執行以下命令確保所有功能正常運作：

```bash
# 1. 提示層
python3 tests/local_ai/test_prompt_profile.py && echo "✓ Prompts OK"

# 2. 檢查層  
python3 tests/local_ai/test_c_checker.py && echo "✓ Checkers OK"

# 3. RAG 層
python3 tests/local_ai/test_rag_search.py && echo "✓ RAG OK"

# 4. 修正循環
python3 tests/local_ai/test_repair_loop.py && echo "✓ Repair OK"

# 5. 離線驗證
python3 tests/local_ai/test_offline_commands.py && echo "✓ Offline OK"

# 6. 完整集成（需要 Ollama + model）
bash local_ai/run.sh --output-format text prompt "寫一個 C 程式" && echo "✓ Integration OK"
```

---

## 11. 快速參考

### 環境變數一覽

```bash
CLAW_MODEL=<model>                    # 指定模型（預設：qwen2.5-coder:14b）
CLAW_OLLAMA_PORT=<port>               # Ollama 埠（預設：11435）
CLAW_PROXY_PORT=<port>                # Proxy 埠（預設：8082）
CLAW_PERMISSION_MODE=<mode>           # 權限模式（預設：read-only）
CLAW_SYSTEM_PROMPT=<text>             # 覆蓋系統提示
CLAW_PROMPT_PROFILE=<profile>         # 提示設定（default_zh_tw/c_programming/project_assistant）
CLAW_PROMPT_DIR=<path>                # 提示目錄（預設：local_ai/prompts）
CLAW_MAX_REPAIR_RETRIES=<int>         # 修復重試（預設：2）
CLAW_RAG_ENABLED=<bool>               # RAG 啟用（由 --rag 自動設定）
CLAW_STRICT_OFFLINE=1                 # 嚴格離線模式（僅允許 bundle binary）
```

### 主要文件路徑

```
local_ai/
├── prompts/                    # 提示策略
├── checkers/                   # 檢查器
├── rag/                        # RAG 文檔庫
│   ├── docs/                   # 導入的文檔
│   ├── index/                  # 索引快取
│   ├── build_index.py
│   ├── search_docs.py
│   └── import_usb_docs.py
├── prompt_loader.py
├── repair_loop.py
├── proxy.py
├── run.sh / run.ps1
└── runtime/                    # 打包 binary + 模型
```

---

## 結論

`research-claw-code` 的四層離線 AI 增強已全部實施並測試完畢：

✅ **第 1 層** - 提示標準化 - 支援多個設定檔、環境變數切換  
✅ **第 2 層** - 本機檢查器 - C/Markdown/安全檢查、JSON 結構化輸出  
✅ **第 3 層** - RAG 文檔庫 - 無向量資料庫、keyword 搜尋、USB 導入  
✅ **第 4 層** - 自動修正循環 - 修復提示、可配置重試、最佳答案保留  

系統完全離線運作，無任何強制網路依賴；所有工具均基於 Python 標準庫與本機文件。可直接搬運到 USB，在無網路機器上離線使用。
