# TEST_RECORD — 實驗性加固測試紀錄

**日期：** 2026-04-13（v1/v2）、2026-04-15（v3）、2026-04-24（v4/v5）
**分支：** `test/experimental-hardening`
**測試執行器：** Python `unittest`（標準庫，無需外部依賴）
**總測試數量（本輪結束後）：** 208（原有 22 + v1 新增 64 + v2 新增 43 + v3 新增 45 + v4 新增 22 + v5 新增 12）— 全數通過 ✅

---

## 假設表格（Hypothesis Table）

### 第一輪（v1）—— 權限、引擎、命令、工具、清單

| # | 假設 | 測試情境 | 預期 | 實際 | 狀態 |
|---|------|---------|------|------|------|
| H1-a | `deny_names` 封鎖不分大小寫 | `blocks("BASHTOOL")` with `deny_names=["BashTool"]` | True | True | ✅ PASS |
| H1-b | `deny_names` 封鎖不分大小寫（小寫） | `blocks("bashtool")` | True | True | ✅ PASS |
| H1-c | `deny_prefixes` 封鎖不分大小寫 | `blocks("MCPTool")` with `deny_prefixes=["mcp"]` | True | True | ✅ PASS |
| H1-d | 空 context 不封鎖任何工具 | `blocks("BashTool")` on empty context | False | False | ✅ PASS |
| H1-e | 多個 deny_names 均有效 | `blocks("BASHTOOL")` and `blocks("fileedittool")` | True × 2 | True × 2 | ✅ PASS |
| H2-a | **BUG** 空 deny_prefix 靜默封鎖所有工具 | `blocks("BashTool")` with `deny_prefixes=[""]` | False（修復後） | False ✅ | **已修復** |
| H2-b | `None` deny_prefixes 安全 | `from_iterables(deny_prefixes=None)` | 不報錯、不封鎖 | 正確 | ✅ PASS |
| H2-c | 純空白前綴無意義 | `deny_prefixes=["   "]` 不封鎖 `"BashTool"` | False | False | ✅ PASS |
| H3-a | 空字串加 0 個 token | `add_turn("", "")` on base `(10, 5)` | `(10, 5)` | `(10, 5)` | ✅ PASS |
| H3-b | 單一單字各加 1 個 token | `add_turn("hello", "world")` | `(1, 1)` | `(1, 1)` | ✅ PASS |
| H3-c | 多單字依 split 計數 | `add_turn("one two three four five", "alpha beta")` | `(5, 2)` | `(5, 2)` | ✅ PASS |
| H3-d | 累積多輪 token 正確 | 兩輪：`"a b"` + `"d e f"` / `"c"` + `"g h"` | `(5, 3)` | `(5, 3)` | ✅ PASS |
| H3-e | `UsageSummary` 不可變 | `add_turn` 後原始物件不變 | `(100, 50)` | `(100, 50)` | ✅ PASS |
| H4-a | `compact(3)` 保留最後 3 筆 | 5 筆 store，compact(3) | `["c","d","e"]` | `["c","d","e"]` | ✅ PASS |
| H4-b | `compact(N)` N = len：無操作 | compact(3) on 3-entry store | 3 筆 | 3 筆 | ✅ PASS |
| H4-c | `compact(N)` N > len：無操作 | compact(10) on 2-entry store | 2 筆 | 2 筆 | ✅ PASS |
| H4-d | **BUG** `compact(0)` 應清空 store | Python `-0 == 0` 導致 `entries[-0:]` 保留全部 | 0 筆（修復後） | 0 筆 ✅ | **已修復** |
| H4-e | `flush()` 設定 `flushed=True` | 呼叫 `flush()` | True | True | ✅ PASS |
| H4-f | `append()` 重置 `flushed` 旗標 | flush 後 append | False | False | ✅ PASS |
| H4-g | `replay()` 回傳 tuple 快照 | 呼叫 `replay()` | `tuple` 型別 | `tuple` | ✅ PASS |
| H5-a | 正常 submit_message 完成 | 1 則訊息，未達上限 | `stop_reason="completed"` | "completed" | ✅ PASS |
| H5-b | 第 9 則訊息在 `max_turns=8` 被攔截 | 填滿 8，嘗試第 9 | `stop_reason="max_turns_reached"` | "max_turns_reached" | ✅ PASS |
| H5-c | `max_turns=0` 攔截第一則訊息 | 嘗試第一則 | `stop_reason="max_turns_reached"` | "max_turns_reached" | ✅ PASS |
| H5-d | 被攔截的訊息不被附加 | 攔截後 message count 不變 | `len` 穩定 | 穩定 | ✅ PASS |
| H5-e | matched_commands 與 tools 反映於結果 | 傳入 `matched_commands=("review",)` | 結果含 "review" | 正確 | ✅ PASS |
| H6-a | `structured_output=True` 輸出合法 JSON | 呼叫 `submit_message("test")` | 可解析 JSON | 可解析 | ✅ PASS |
| H6-b | JSON 包含 prompt 文字 | 送出 "find security issues" | summary 含 prompt | 正確 | ✅ PASS |
| H7-a | 串流第一個事件為 `message_start` | `stream_submit_message("hello")` | first type = "message_start" | 正確 | ✅ PASS |
| H7-b | 串流最後一個事件為 `message_stop` | 同上 | last type = "message_stop" | 正確 | ✅ PASS |
| H7-c | `message_stop` 含 `stop_reason` 與 `usage` | 同上 | 兩個鍵都存在 | 正確 | ✅ PASS |
| H7-d | 有 commands 時發出 `command_match` 事件 | 傳入 `matched_commands=("review",)` | 事件型別存在 | 正確 | ✅ PASS |
| H7-e | 有 tools 時發出 `tool_match` 事件 | 傳入 `matched_tools=("BashTool",)` | 事件型別存在 | 正確 | ✅ PASS |
| H7-f | 無 commands 時不發出 `command_match` | 不傳 matched_commands | 事件型別缺席 | 缺席 | ✅ PASS |
| H7-g | 有 denied_tools 時發出 `permission_denial` | 傳入 `denied_tools=(denial,)` | 事件型別存在 | 正確 | ✅ PASS |
| H8-a | `get_command` 不分大小寫 | `get_command(name.upper())` | Not None | Not None | ✅ PASS |
| H8-b | `get_command` 未知命令 → None | `get_command("zzz_xyz")` | None | None | ✅ PASS |
| H8-c | `get_command("")` → None（對抗性） | `get_command("")` | None | None | ✅ PASS |
| H8-d | `execute_command` 已知 → `handled=True` | 已知命令名稱 | `handled=True` | 正確 | ✅ PASS |
| H8-e | `execute_command` 未知 → `handled=False` | 未知命令 | `handled=False` | 正確 | ✅ PASS |
| H8-f | `find_commands("")` 回傳全部（邊界） | 空查詢 | 全部命令 | 全部匹配 | ✅ PASS |
| H8-g | `find_commands("zzz_no_match")` → 空 | 無匹配查詢 | `[]` | `[]` | ✅ PASS |
| H8-h | `get_commands(include_plugin_commands=False)` 過濾 | 外掛過濾器 | 子集 ≤ 全集 | 正確 | ✅ PASS |
| H9-a | `None` context 回傳全部工具 | `filter_tools_by_permission_context(tools, None)` | 完整列表 | 完整列表 | ✅ PASS |
| H9-b | deny name 移除精確的那個工具 | 拒絕第一個工具 by name | 該工具缺席 | 缺席 | ✅ PASS |
| H9-c | deny prefix `"mcp"` 移除所有 MCP 工具 | `deny_prefixes=["mcp"]` | 無 `mcp*` 工具殘留 | 正確 | ✅ PASS |
| H9-d | 空 deny_names → 不移除任何工具 | `deny_names=[]` | 完整列表 | 完整列表 | ✅ PASS |
| H10-a | 空 temp dir → 0 個 Python 檔案 | `build_port_manifest(Path(tmp_empty))` | `total_python_files=0` | 0 | ✅ PASS |
| H10-b | 一個 `.py` → 計數 1 | 1 個 `.py` 在 temp | `total_python_files=1` | 1 | ✅ PASS |
| H10-c | 非 `.py` 檔案被忽略 | `.py` + `.txt` + `.json` | `total_python_files=1` | 1 | ✅ PASS |
| H10-d | 巢狀 `.py` 檔案計入 | 3 個 `.py` 在樹中 | `total_python_files=3` | 3 | ✅ PASS |
| H10-e | `to_markdown()` 提及 root 與計數 | 呼叫 `to_markdown()` | 含 "Port root:" 與 "Total Python files:" | 正確 | ✅ PASS |
| H11-a | `ExecutionRegistry.command()` 不分大小寫 | `.upper()` / `.lower()` 查詢 | Not None | 正確 | ✅ PASS |
| H11-b | `ExecutionRegistry.tool()` 不分大小寫 | 同上 | Not None | 正確 | ✅ PASS |
| H11-c | 缺少命令 → None | `command("ghost_xyz")` | None | None | ✅ PASS |
| H11-d | 缺少工具 → None | `tool("ghost_xyz")` | None | None | ✅ PASS |
| H11-e | 找到命令 execute → mirrored 訊息 | `cmd.execute("input")` | 含 "Mirrored command" | 正確 | ✅ PASS |
| H11-f | 找到工具 execute → mirrored 訊息 | `tool.execute("payload")` | 含 "Mirrored tool" | 正確 | ✅ PASS |
| H12-a | 空 `PortingBacklog.summary_lines()` | `PortingBacklog(title="empty")` | `[]` | `[]` | ✅ PASS |
| H12-b | 行數 == 模組數 | `build_command_backlog()` | 長度相等 | 相等 | ✅ PASS |
| H12-c | 每行含模組名稱 | 前 5 個模組 | 名稱在行中 | 正確 | ✅ PASS |
| H12-d | 每行含 `[mirrored]` 狀態 | 前 5 行 | `[mirrored]` 在行中 | 正確 | ✅ PASS |

### 第二輪（v2）—— 成本追蹤、歷史紀錄、延遲初始化、上下文、Prefetch

| # | 假設 | 測試情境 | 預期 | 實際 | 狀態 |
|---|------|---------|------|------|------|
| H13-a | `CostTracker` 初始狀態為零 | 新建實例 | `total_units=0`, `events=[]` | 正確 | ✅ PASS |
| H13-b | 單次 record 正確加總 | `record("step", 5)` | `total_units=5` | 5 | ✅ PASS |
| H13-c | 多次 record 累積 | 3 次 record 合計 20 | 20 | 20 | ✅ PASS |
| H13-d | 事件格式為 `label:units` | `record("tokenize", 42)` | `["tokenize:42"]` | `["tokenize:42"]` | ✅ PASS |
| H13-e | 零 units 正常記錄 | `record("noop", 0)` | `total_units=0`，事件存在 | 正確 | ✅ PASS |
| H13-f | 大量 record 正確累積 | 1000 次 × 1 unit | `total_units=1000` | 1000 | ✅ PASS |
| H14-a | **BUG** 負數 units 不應讓 total 變負 | `record("attack", -999)` after `record("positive", 10)` | `total_units >= 0`（修復後） | 0 以上 ✅ | **已修復** |
| H14-b | 僅負數 record 不應讓 total 低於 0 | `record("neg", -1)` | `total_units >= 0` | 0 ✅ | **已修復** |
| H15-a | `apply_cost_hook` 回傳同一個 tracker | 呼叫 hook | `returned is ct` | True | ✅ PASS |
| H15-b | hook 後 units 已累積 | `apply_cost_hook(ct, "event", 7)` | `total_units=7` | 7 | ✅ PASS |
| H15-c | 零 units hook 不改變 total | `apply_cost_hook(ct_100, "noop", 0)` | `total_units=100` | 100 | ✅ PASS |
| H16-a | 空 `HistoryLog` 僅有標題 | `as_markdown()` on empty log | 含 "# Session History"，無 "- " | 正確 | ✅ PASS |
| H16-b | 單筆事件出現在 markdown | `add("Login", "user authenticated")` | 含 "Login" 與 "user authenticated" | 正確 | ✅ PASS |
| H16-c | 多筆事件全部出現 | 3 筆 add | 全部標題出現 | 正確 | ✅ PASS |
| H16-d | markdown 行數與事件數一致 | 5 筆事件 | 5 個 `"- "` 行 | 5 | ✅ PASS |
| H16-e | `HistoryEvent` 欄位可存取 | `event.title`, `event.detail` | 正確值 | 正確 | ✅ PASS |
| H16-f | 空字串 title/detail 不拋例外（Edge） | `add("", "")` | 不報錯 | 不報錯 | ✅ PASS |
| H17-a | `trusted=True` 啟用所有功能 | `run_deferred_init(True)` | 所有旗標 True | True | ✅ PASS |
| H17-b | `trusted=False` 停用所有功能 | `run_deferred_init(False)` | 所有旗標 False | False | ✅ PASS |
| H17-c | `trusted` 旗標反映於 result | 比對 `.trusted` 欄位 | True/False 對應 | 正確 | ✅ PASS |
| H17-d | `as_lines()` 回傳 4 個項目 | 計算 lines 長度 | 4 | 4 | ✅ PASS |
| H17-e | `as_lines()` 含 `plugin_init=True` | 文字搜尋 | 存在 | 存在 | ✅ PASS |
| H17-f | `as_lines()` 不輸出 `trusted` 欄位（設計如此） | 文字搜尋 | 不含 "trusted=" | 不含 | ✅ PASS |
| H18-a | 空 temp dir 所有計數為 0 | `build_port_context(Path(tmp))` | 全部 0，archive_available=False | 正確 | ✅ PASS |
| H18-b | src/ 中的 Python 檔案計入 | 2 個 `.py` 在 src/ | `python_file_count=2` | 2 | ✅ PASS |
| H18-c | tests/ 中的測試檔案計入 | 1 個 `.py` 在 tests/ | `test_file_count=1` | 1 | ✅ PASS |
| H18-d | archive 目錄存在時 `archive_available=True` | 建立 archive 路徑 | True | True | ✅ PASS |
| H18-e | `render_context()` 含所有鍵 | 文字搜尋 | 含 "Source root:" 等 | 正確 | ✅ PASS |
| H19-a | `start_mdm_raw_read()` 回傳 `started=True` | 呼叫函式 | `started=True`, `name="mdm_raw_read"` | 正確 | ✅ PASS |
| H19-b | `start_keychain_prefetch()` 回傳 `started=True` | 呼叫函式 | `started=True` | 正確 | ✅ PASS |
| H19-c | `start_project_scan()` 掃描現有路徑 | 傳入 temp dir | `started=True`，detail 含路徑 | 正確 | ✅ PASS |
| H19-d | `start_project_scan()` 即使路徑不存在也 `started=True`（Edge） | 傳入 `/nonexistent` | `started=True`（模擬） | True | ✅ PASS |
| H19-e | 所有 prefetch result 的 `detail` 非空 | 兩個函式 | `bool(r.detail)` = True | True | ✅ PASS |
| H20-a | `QueryRequest` 儲存 prompt | `QueryRequest(prompt="find bugs")` | `req.prompt == "find bugs"` | 正確 | ✅ PASS |
| H20-b | `QueryResponse` 儲存 text | `QueryResponse(text="result")` | `resp.text == "result"` | 正確 | ✅ PASS |
| H20-c | `QueryRequest` 不可變 | 嘗試修改 `req.prompt` | 拋出例外 | 拋出 | ✅ PASS |
| H20-d | `QueryResponse` 不可變 | 嘗試修改 `resp.text` | 拋出例外 | 拋出 | ✅ PASS |
| H20-e | 空 prompt 有效（Edge） | `QueryRequest(prompt="")` | 不報錯 | 不報錯 | ✅ PASS |
| H20-f | 純空白 prompt 原樣保留（Edge） | `QueryRequest(prompt="   ")` | `req.prompt == "   "` | 正確 | ✅ PASS |
| H21-a | 回歸：Bug 1 空前綴不再封鎖所有工具 | `deny_prefixes=[""]` | 全部 False | False | ✅ PASS |
| H21-b | 回歸：Bug 2 `compact(0)` 清空 | 5 筆 store → compact(0) | 0 筆 | 0 筆 | ✅ PASS |
| H21-c | 回歸：Bug 2 單筆 compact(0) | 1 筆 store → compact(0) | 0 筆 | 0 筆 | ✅ PASS |
| H21-d | 回歸：Bug 1 空白前綴不封鎖 | `deny_prefixes=["  "]` | False | False | ✅ PASS |

---

## 發現問題清單

### Bug 1 — `ToolPermissionContext`：空 `deny_prefix` 靜默封鎖所有工具

**檔案：** `src/permissions.py`
**嚴重程度：** 高
**類別：** 對抗性輸入 / 安全性設定錯誤

**說明：**
`ToolPermissionContext.from_iterables(deny_prefixes=[""])` 建立的 context 會封鎖所有工具。原因是 Python 的 `str.startswith("")` 永遠回傳 `True`，因此任何空字串前綴都會比對所有工具名稱。設定中出現一個空項目就會靜默停用所有工具，不報任何錯誤或警告。

**根本原因：** `from_iterables` 未驗證前綴值，空字串直接轉小寫後儲存。

**修復內容：**
```python
deny_prefixes=tuple(
    p for p in (prefix.lower() for prefix in (deny_prefixes or []))
    if p.strip()
),
```

---

### Bug 2 — `TranscriptStore.compact(0)`：Python `-0 == 0` 陷阱保留所有紀錄

**檔案：** `src/transcript.py`
**嚴重程度：** 中
**類別：** 邊界邏輯 / off-by-one

**說明：**
呼叫 `compact(keep_last=0)` 應將 transcript 清空為零筆。但由於 Python 中 `-0 == 0`，`entries[-0:]` 等同於 `entries[0:]`（完整切片），導致所有紀錄被保留。同樣的問題在 `QueryEnginePort.compact_messages_if_needed` 中也隱含存在。

**根本原因：** Python 整數不區分 `-0` 與 `0`，切片 `seq[-0:]` 等同 `seq[0:]`。

**修復內容：**
```python
if keep_last == 0:
    self.entries.clear()
else:
    self.entries[:] = self.entries[-keep_last:]
```

---

### Bug 3 — `CostTracker.record()`：負數 units 讓 total_units 變成負數

**檔案：** `src/cost_tracker.py`
**嚴重程度：** 中
**類別：** 輸入驗證缺失 / 計費邏輯錯誤

**說明：**
呼叫 `record("label", -999)` 會讓 `total_units` 降為負數。記錄負成本在語意上不合理（沒有「退款」情境），且可能讓呼叫端以為用量少於實際，造成計費錯誤或閾值邏輯失效。

**探測輸出：**
```
ct.record("positive", 10)
ct.record("attack", -999)
ct.total_units  →  -989   # 預期 >= 0
```

**根本原因：** `record()` 直接將 `units` 加入 `total_units`，未做任何非負驗證。

**修復內容：**
```python
safe_units = max(0, units)
self.total_units += safe_units
self.events.append(f'{label}:{safe_units}')
```

---

### 第三輪（v3）—— session_store、parity_audit、remote_runtime、query_engine 深層路徑

| # | 假設 | 測試情境 | 預期 | 實際 | 狀態 |
|---|------|---------|------|------|------|
| H22-a | `load_session` 對缺少檔案拋出 `FileNotFoundError` 且含 session_id | `load_session('nonexistent')` | `FileNotFoundError` + session_id 在訊息中 | 正確 | ✅ PASS |
| H22-b | 錯誤訊息提及檔案路徑 | 同上 | 路徑出現於訊息 | 正確 | ✅ PASS |
| H22-c | **BUG** 損壞 JSON 拋出 `ValueError` 含 session_id | `load_session('bad_json')` | `ValueError` 含 session_id（修復後） | 正確 ✅ | **已修復** |
| H22-d | **BUG** 欄位缺失拋出 `ValueError` 列出缺少欄位 | `load_session('partial')` | `ValueError` 列出 `messages` | 正確 ✅ | **已修復** |
| H23-a | `archive_present=False` → markdown 含 "unavailable" | `to_markdown()` | 含不可用說明，不含覆蓋率 | 正確 | ✅ PASS |
| H23-b | `archive_present=True` → markdown 含覆蓋率數值 | `to_markdown()` with 15/18 | 含 "15/18" | 正確 | ✅ PASS |
| H23-c | 無缺少目標 → markdown 顯示 "none" | 所有目標均存在 | 含 "none" | 正確 | ✅ PASS |
| H23-d | 有缺少目標 → markdown 列出名稱 | `missing_root_targets=('foo.py', 'bar.py')` | 名稱出現 | 正確 | ✅ PASS |
| H23-e | `run_parity_audit()` 不拋出例外 | 呼叫函式 | 回傳 `ParityAuditResult` | 正確 | ✅ PASS |
| H23-f | 覆蓋率分子 ≤ 分母 | 驗證比例合理性 | 兩個比率均合理 | 正確 | ✅ PASS |
| H24-a | `run_remote_mode` 回傳 `connected=True` | 呼叫函式 | True | True | ✅ PASS |
| H24-b | remote mode detail 含 target 字串 | `run_remote_mode('prod-server')` | 含 "prod-server" | 正確 | ✅ PASS |
| H24-c | SSH mode `mode` 欄位為 'ssh' | `run_ssh_mode(...)` | "ssh" | "ssh" | ✅ PASS |
| H24-d | SSH mode detail 含 target | `run_ssh_mode('my-host')` | 含 "my-host" | 正確 | ✅ PASS |
| H24-e | Teleport mode `mode` 欄位為 'teleport' | `run_teleport_mode(...)` | "teleport" | "teleport" | ✅ PASS |
| H24-f | `as_text()` 含 mode=, connected=, detail= | 直接建立 `RuntimeModeReport` | 三鍵均出現 | 正確 | ✅ PASS |
| H24-g | `RuntimeModeReport` 為 frozen，不可修改 | 嘗試 `report.mode = 'altered'` | 拋出例外 | 拋出 | ✅ PASS |
| H24-h | 空 target 字串不拋出例外（Edge） | `run_remote_mode('')` | 回傳有效物件 | 正確 | ✅ PASS |
| H25-a | **BUG** budget 耗盡後 `mutable_messages` 不再成長 | 持續 submit 後檢查長度 | 長度固定（修復後） | 固定 ✅ | **已修復** |
| H25-b | budget 超出時 `stop_reason='max_budget_reached'` | `max_budget_tokens=1` | 'max_budget_reached' | 正確 | ✅ PASS |
| H25-c | budget 未耗盡時正常 append | 送兩則訊息 | `len=2` | 2 | ✅ PASS |
| H25-d | budget 耗盡後 `transcript_store.entries` 不再成長 | 同 H25-a | 長度固定 | 固定 ✅ | **已修復** |
| H25-e | budget 耗盡後仍回傳有效 `TurnResult` | 同上 | result 非 None | 正確 | ✅ PASS |
| H26-a | 訊息超過 `compact_after_turns` 時觸發截斷 | 送 5 則，threshold=3 | `len ≤ 3` | ≤ 3 | ✅ PASS |
| H26-b | 未超過閾值時不觸發 compaction | 送 3 則，threshold=10 | `len=3` | 3 | ✅ PASS |
| H26-c | transcript_store 與 messages 同步壓縮 | 送 6 則，threshold=3 | `len(entries) ≤ 3` | ≤ 3 | ✅ PASS |
| H26-d | compaction 後 `replay_user_messages` 回傳保留部分 | 送 5 則，threshold=2 | `len(replayed) ≤ 2` | ≤ 2 | ✅ PASS |
| H27-a | persist 後 restore，messages 內容一致 | persist → from_saved_session | 相等 | 相等 | ✅ PASS |
| H27-b | restore 後 session_id 一致 | 同上 | session_id 相等 | 正確 | ✅ PASS |
| H27-c | restore 後 token usage 數值一致 | 送訊息後 persist/restore | input/output tokens 相等 | 相等 | ✅ PASS |
| H27-d | 空 session persist + restore 不拋出 | 無訊息就 persist | 回傳空 messages | 正確 | ✅ PASS |
| H28-a | `render_summary` 含 session_id | 呼叫 `render_summary()` | session_id 出現 | 出現 | ✅ PASS |
| H28-b | `render_summary` 顯示 max_turns 值 | `max_turns=5` | 含 '5' | 正確 | ✅ PASS |
| H28-c | `render_summary` 含 workspace 字樣 | 標準呼叫 | 含 "Python Porting Workspace" | 正確 | ✅ PASS |
| H28-d | `render_summary` turn count 反映 submit 次數 | 送兩則後 render | 含 '2' | 正確 | ✅ PASS |
| H29-a | 回歸：Bug 4 — budget 耗盡後 messages 不成長 | 同 H25-a | 長度固定 | 固定 | ✅ PASS |
| H29-b | 回歸：Bug 5 — 缺少 session 拋出 `FileNotFoundError` | 同 H22-a | `FileNotFoundError` | 正確 | ✅ PASS |
| H29-c | 回歸：Bug 5 — 損壞 JSON 拋出 `ValueError` | 同 H22-c | `ValueError` | 正確 | ✅ PASS |
| H29-d | 回歸：Bug 5 — 欄位缺失 `ValueError` 含欄位名 | 同 H22-d | 含 `input_tokens` 或 `output_tokens` | 正確 | ✅ PASS |
| H30-a | save_session 回傳路徑確實存在 | 儲存後驗證路徑 | `Path.exists()=True` | True | ✅ PASS |
| H30-b | save/load roundtrip — session_id | 完整回路 | 相等 | 相等 | ✅ PASS |
| H30-c | save/load roundtrip — messages 類型為 tuple | JSON→list→tuple 轉換 | `isinstance(..., tuple)` | True | ✅ PASS |
| H30-d | save/load roundtrip — 空 messages | `messages=()` | `()` | `()` | ✅ PASS |
| H30-e | save/load roundtrip — token counts | `input=999, output=42` | 數值相等 | 相等 | ✅ PASS |

---

## 發現問題清單

### Bug 4 — `QueryEnginePort.submit_message`：`max_budget_reached` 後仍累積訊息

**檔案：** `src/query_engine.py`
**嚴重程度：** 高
**類別：** 計費邏輯 / 無限成長

**說明：**
當 `projected_usage.input_tokens + projected_usage.output_tokens > max_budget_tokens` 時，`stop_reason` 設為 `'max_budget_reached'`，但程式仍繼續執行 `self.mutable_messages.append(prompt)` 和 `self.transcript_store.append(prompt)`。換言之，就算預算已耗盡，每一次 `submit_message` 呼叫都會讓對話串無限成長，最終導致記憶體壓力，並讓呼叫端誤以為 stop_reason 已阻止了進一步處理。

**根本原因：** `stop_reason` 邏輯改寫後，append 操作沒有跟著加上防護條件。

**修復內容：**
```python
if stop_reason == 'completed':
    self.mutable_messages.append(prompt)
    self.transcript_store.append(prompt)
    self.permission_denials.extend(denied_tools)
    self.total_usage = projected_usage
    self.compact_messages_if_needed()
else:
    # Budget exhausted: record denials and usage but do not grow the conversation.
    self.permission_denials.extend(denied_tools)
    self.total_usage = projected_usage
```

---

### Bug 5 — `session_store.load_session`：缺少/損壞/欄位不足時錯誤訊息不具診斷性

**檔案：** `src/session_store.py`
**嚴重程度：** 中
**類別：** 錯誤處理 / 可觀測性

**說明：**
原本的 `load_session` 直接呼叫 `.read_text()` 並存取 `data['session_id']` 等欄位，錯誤情境如下：
- 檔案不存在 → Python 拋出通用 `FileNotFoundError`，訊息僅含路徑，不含 session_id
- JSON 損壞 → `json.JSONDecodeError` 直接外漏，無 session 上下文
- 欄位缺失 → `KeyError`，沒有說明哪個 session 或哪些欄位有問題

這讓 session 復原的錯誤難以追蹤，尤其在多 session 環境下。

**修復內容：**
```python
if not session_path.exists():
    raise FileNotFoundError(
        f"Session '{session_id}' not found at {session_path}. ..."
    )
try:
    data = json.loads(session_path.read_text())
except json.JSONDecodeError as exc:
    raise ValueError(f"Session '{session_id}' has corrupted JSON ...") from exc
missing = [k for k in ('session_id', 'messages', 'input_tokens', 'output_tokens') if k not in data]
if missing:
    raise ValueError(f"Session '{session_id}' is missing required fields: {missing}")
```

---

## Rust 靜態分析（新增，第三輪）

`cargo` 在測試沙箱中不可用，以下為靜態程式碼分析結論。現有 Rust 測試由 CI（`rust-ci.yml`）驗證。

### 已確認的邊界案例

| 模組 | 發現 | 嚴重程度 | 備註 |
|------|------|---------|------|
| `bash_validation.rs` | `extract_first_command` 以空白分割，`"ls; rm -rf /"` 的 `first_command = "ls;"` 不匹配任何封鎖命令 — 分號鏈接的寫入命令可繞過 read-only 檢查 | **高** | 建議：在提取前先以 `;`、`&&`、`\|\|` 分割，對每個子命令分別驗證 |
| `bash_validation.rs` | `check_destructive` 使用子字串比對（`rm -rf /`），`rm -fr /`、`rm -r -f /` 等參數重排變體不被偵測 | 中 | 建議：正規化 `-rf`/`-fr`/`-r -f` 為標準形式後比對 |
| `bash_validation.rs` | `validate_read_only` 的 `>` 重導向偵測：`echo "a > b"` 含有 `>` 字符但不是重導向，可能產生誤攔 | 低 | 現有行為較保守（誤攔 > 漏攔），可接受 |
| `bash_validation.rs` | `validate_paths` 的 `~/` 偵測：`echo "my ~/path"` 中的 `~` 在字串內，但仍觸發 Warn | 低 | 啟發式規則，刻意保守 |
| `config.rs` | `ProviderFallbackConfig` 無最大長度限制 — 理論上 fallback 鏈可無限長 | 低 | 實務上不影響現有功能 |

---

## 修復摘要

| 檔案 | 修改內容 | 影響行數 |
|------|---------|---------|
| `src/permissions.py` | 在 `from_iterables` 中過濾空/空白 deny_prefixes | +4（註解 + 過濾運算式） |
| `src/transcript.py` | 在 `compact(0)` 加入明確的 `clear()` 分支 | +4（註解 + 分支） |
| `src/cost_tracker.py` | 在 `record()` 中以 `max(0, units)` 截斷負數 | +3（註解 + safe_units） |
| `src/permissions.py` | 在 `from_iterables` 中過濾空/空白 deny_prefixes | +4（註解 + 過濾運算式） |
| `src/transcript.py` | 在 `compact(0)` 加入明確的 `clear()` 分支 | +4（註解 + 分支） |
| `src/cost_tracker.py` | 在 `record()` 中以 `max(0, units)` 截斷負數 | +3（註解 + safe_units） |
| `src/query_engine.py` | **Bug 4** — submit_message 在 budget 超出時不再 append（+14 行） | 新增條件分支 |
| `src/session_store.py` | **Bug 5** — load_session 加入檔案存在檢查、JSON 解析保護、欄位驗證（+16 行） | 新增錯誤處理 |
| `tests/test_experimental_hardening.py` | 64 個新測試（v1），12 個測試類別 | 新增檔案 |
| `tests/test_experimental_hardening_v2.py` | 43 個新測試（v2），9 個測試類別 | 新增檔案 |
| `tests/test_experimental_hardening_v3.py` | 45 個新測試（v3），9 個測試類別 | 新增檔案 |

---

## 測試執行結果

```
Ran 174 tests in 3.142s
OK
```

所有 174 個測試通過（原有 22 個 + v1 新增 64 個 + v2 新增 43 個 + v3 新增 45 個）。

### 新增測試檔案結構

**v1 — `tests/test_experimental_hardening.py`（64 個測試）**

| 測試類別 | 測試數 | 覆蓋範圍 |
|---------|-------|---------|
| `TestToolPermissionContextCaseInsensitivity` | 7 | 不分大小寫封鎖 |
| `TestToolPermissionContextAdversarialEmptyPrefix` | 3 | **Bug 1** 對抗性前綴輸入 |
| `TestUsageSummaryTokenCounting` | 5 | Token 累積語意 |
| `TestTranscriptStoreCompact` | 7 | **Bug 2** compact(0) + flush/append |
| `TestQueryEngineMaxTurns` | 5 | max_turns 邊界執行 |
| `TestQueryEngineStructuredOutput` | 2 | JSON 輸出合法性 |
| `TestQueryEngineStreamEvents` | 7 | SSE 事件順序與型別 |
| `TestCommandsModuleRobustness` | 9 | 不分大小寫查詢、對抗性輸入 |
| `TestToolsPermissionFiltering` | 4 | 工具權限管控 |
| `TestPortManifestCustomRoot` | 5 | 自訂路徑的檔案計數 |
| `TestExecutionRegistryLookup` | 6 | 註冊表不分大小寫查詢 |
| `TestPortingBacklogSummaryLines` | 4 | summary line 格式正確性 |

**v2 — `tests/test_experimental_hardening_v2.py`（43 個測試）**

| 測試類別 | 測試數 | 覆蓋範圍 |
|---------|-------|---------|
| `TestCostTrackerNormalBehaviour` | 6 | 正常累積行為 |
| `TestCostTrackerAdversarialNegativeUnits` | 2 | **Bug 3** 負數 units 對抗性輸入 |
| `TestApplyCostHook` | 3 | apply_cost_hook 回傳與累積 |
| `TestHistoryLogMarkdown` | 6 | markdown 格式正確性 |
| `TestDeferredInit` | 6 | trusted/untrusted 旗標行為 |
| `TestPortContext` | 5 | 目錄計數與 archive 偵測 |
| `TestPrefetchResult` | 5 | prefetch 函式 started/name/detail |
| `TestQueryDataClasses` | 6 | QueryRequest/QueryResponse 不可變性 |
| `TestRegressionBug1And2` | 4 | Bug 1 與 Bug 2 回歸驗證 |

**v3 — `tests/test_experimental_hardening_v3.py`（45 個測試）**

| 測試類別 | 測試數 | 覆蓋範圍 |
|---------|-------|---------|
| `TestSessionStoreRoundtrip` | 6 | save/load 完整回路、類型保留 |
| `TestSessionStoreErrorHandling` | 4 | **Bug 5** 缺少/損壞/欄位不足的錯誤處理 |
| `TestParityAuditMarkdown` | 6 | archive 存在與否、覆蓋率顯示、缺少目標 |
| `TestRemoteRuntimeReports` | 8 | 三種 mode、as_text 格式、不可變性、Edge case |
| `TestQueryEngineBudgetExhaustion` | 5 | **Bug 4** max_budget_reached 不再累積訊息 |
| `TestQueryEngineCompaction` | 4 | compact_after_turns 觸發時機與 transcript 同步 |
| `TestQueryEngineSessionPersistence` | 4 | persist + from_saved_session 回路 |
| `TestQueryEngineRenderSummary` | 4 | render_summary 完整性 |
| `TestRegressionBug4And5` | 4 | Bug 4 與 Bug 5 回歸驗證 |

---

## Rust 程式碼庫說明（沙箱無 cargo 環境）

`rust/` 工作區包含大量 inline 單元測試與整合測試：

- `rust/crates/runtime/src/permissions.rs` — 11 個 `#[test]`，涵蓋 `PermissionPolicy`、hook override、規則式 allow/deny/ask
- `rust/crates/runtime/src/bash_validation.rs` — 32 個 `#[test]`，涵蓋唯讀驗證、破壞性命令警告、sed/path 驗證
- `rust/crates/runtime/tests/integration_tests.rs` — 跨模組接線測試（stale branch → policy engine、green contracts）
- `rust/crates/rusty-claude-cli/tests/` — CLI 旗標預設值、compact 輸出、mock parity harness、輸出格式合約、resume/slash 命令

這些測試由 CI（`rust-ci.yml`）驗證，在具備穩定 Rust 工具鏈的機器上執行 `cargo test --workspace` 應全數通過。

第三輪靜態分析新發現（詳見上方「Rust 靜態分析」段落）：最高優先級項目為 `bash_validation.rs` 的分號鏈接繞過問題，建議在 `extract_first_command` 之前先對命令字串進行 shell operator splitting（`;`、`&&`、`||`、`|`），對每個子命令段落分別驗證。

---

## 第四輪（v4）—— Proxy 層離線行為與 zh-TW 強化

**日期：** 2026-04-24
**新增測試數：** 22（累積 196）
**測試檔：** `tests/test_experimental_hardening_v4_proxy.py`
**執行指令：** `python3 tests/test_experimental_hardening_v4_proxy.py`
**執行結果：** `Ran 22 tests in 0.621s — OK` ✅
**受測模組：** `local_ai/proxy.py`（Anthropic ↔ Ollama 轉譯 proxy，純 stdlib 實作）

### 背景

v1–v3 聚焦於 Python port（`src/`）的權限、引擎、命令、session 與 query 子系統。v4 把範圍延伸到離線執行路徑上最關鍵的單元：`local_ai/proxy.py`。這個 proxy 是 bundle 執行時 `claw` CLI 與 bundled Ollama 之間的唯一橋樑，同時負責：

1. Anthropic Messages API ↔ Ollama OpenAI-compatible `/v1/chat/completions` 雙向轉譯
2. C 語言題目的本地靜態檢查 + 重寫迴圈（最多 2 次重試）
3. 一般問題的真實 SSE 串流 passthrough
4. 所有錯誤訊息一律以 zh-TW UTF-8 輸出

### 假設表格（Hypothesis Table）

| # | 假設 | 測試情境 | 預期 | 實際 | 狀態 |
|---|------|---------|------|------|------|
| H-v4-01 | 語言偵測：顯式 Python 關鍵字命中 | `detect_language("請幫我寫 python 的快排")` | `"python"` | `"python"` | ✅ PASS |
| H-v4-02 | 語言偵測：顯式 Java 關鍵字命中 | `detect_language("用 Java 寫 fibonacci")` | `"java"` | `"java"` | ✅ PASS |
| H-v4-03 | 語言偵測：C++ 不會誤判為 C | 含 `c++` 字樣 | `"cpp"`（非 `"c"`） | `"cpp"` | ✅ PASS |
| H-v4-04 | 語言偵測：未指定語言預設 C | 單純「幫我寫排序」 | `"c"` | `"c"` | ✅ PASS |
| H-v4-05 | 語言偵測：非程式題回傳 None | 「今天天氣如何」 | `None` | `None` | ✅ PASS |
| H-v4-06 | 靜態 C 檢查：最小合法 C 通過 | `#include <stdio.h>` + `int main` | `ok=True` | `True` | ✅ PASS |
| H-v4-07 | 靜態 C 檢查：缺少 `main` 被拒 | 只有函式宣告 | `ok=False` | `False` | ✅ PASS |
| H-v4-08 | 靜態 C 檢查：拒絕 `std::` 命名空間 | `std::cout` 代碼片段 | `ok=False` | `False` | ✅ PASS |
| H-v4-09 | 靜態 C 檢查：拒絕 `cout` | iostream 風格輸出 | `ok=False` | `False` | ✅ PASS |
| H-v4-10 | 靜態 C 檢查：拒絕 `vector<>` 模板 | `std::vector<int>` | `ok=False` | `False` | ✅ PASS |
| H-v4-11 | 級數數學檢查：hello world 被判不達題意 | 輸出 hello 的 C 程式 | 不通過 | 不通過 | ✅ PASS |
| H-v4-12 | 級數數學檢查：級數題缺 `factorial` 被拒 | `sin(x)` 展開題目但沒 factorial | 不通過 | 不通過 | ✅ PASS |
| H-v4-13 | `_send_json_error` 中文 UTF-8 往返保留原字元 | 中文錯誤訊息 | 位元組含原始中文 UTF-8 | 保留 | ✅ PASS |
| H-v4-14 | 舊行為（`ensure_ascii=True`）會把中文跳脫為 `\uXXXX` | 對照實驗 | 含 `\u` 跳脫序列 | 確認差異 | ✅ PASS |
| H-v4-15 | SSE 生成器：`text_to_anthropic_sse` 事件順序正確 | 純文字轉 SSE | `message_start` → `content_block_start` → `content_block_delta` → `content_block_stop` → `message_delta` → `message_stop` | 順序正確 | ✅ PASS |
| H-v4-16 | SSE 生成器：中文 token 不被破壞 | 含 `「繁體中文」` 的 delta | UTF-8 原字元保留 | 保留 | ✅ PASS |
| H-v4-17 | 端到端：`/health` 回 200 與 JSON | 起 proxy，call `GET /health` | 200 + JSON | 正確 | ✅ PASS |
| H-v4-18 | 端到端：非串流 zh-TW 回覆 | `stream=False` 的 Messages call | Anthropic 格式 + 中文內容 | 正確 | ✅ PASS |
| H-v4-19 | 端到端：串流真實 SSE（非 C 題） | `stream=True` 一般問題 | 多個 SSE 事件、含 `message_start`、`message_stop` | 真串流 | ✅ PASS |
| H-v4-20 | 端到端：未知端點回 zh-TW UTF-8 錯誤 | `POST /v99/unknown` | 4xx + 中文 `未知的端點：` | 正確 | ✅ PASS |
| H-v4-21 | 端到端：非法 JSON body 回 zh-TW UTF-8 錯誤 | POST `{bad json` | 4xx + 中文 `請求內容不是合法的 JSON` | 正確 | ✅ PASS |
| H-v4-22 | 端到端：C 題第一次回 C++ 被拒、第二次修復後通過 | Fake Ollama 第 1 次回 `cout`，第 2 次回 `printf` | 第二輪輸出為合法 C | 正確 | ✅ PASS |

### 測試類別分佈

| 測試類別 | 測試數 | 覆蓋範圍 |
|---------|-------|---------|
| `TestLanguageDetection` | 5 | 程式語言偵測的多語系輸入（python/java/c++/c/non-code） |
| `TestStaticCCheck` | 5 | C 語法/結構靜態檢查與 C++ 特徵拒絕 |
| `TestSeriesMathCheck` | 2 | 級數題的語意級健全性檢查 |
| `TestSendJsonErrorBytes` | 2 | 錯誤訊息 UTF-8 位元組保證（對照舊 `ensure_ascii=True` 行為） |
| `TestSseGenerators` | 2 | Anthropic SSE 事件序列與中文 token 保真 |
| `EndToEndProxy` | 6 | 子行程啟動真實 `proxy.py` 並以 Fake Ollama HTTP server 打端到端 |

### 端到端測試架構

`EndToEndProxy.setUpClass` 建立完整的離線執行鏡像：

1. 挑兩個空閒 port（`socket.SOCK_STREAM` + `getsockname()[1]`），分別當 fake Ollama 與 proxy 的 port
2. 啟動 `ThreadingHTTPServer` 承載 `FakeOllamaHandler`，支援：
   - `GET /api/tags` — 回模型列表
   - `POST /v1/chat/completions`（`stream=False`）— 回固定中文 JSON
   - `POST /v1/chat/completions`（`stream=True`）— 逐 chunk 發 OpenAI SSE
   - 以 `shared_state` 控制 C 修復流程：第 1 次回 `std::cout`、第 2 次回合法 C
3. `subprocess.Popen` 起一份真實 `local_ai/proxy.py`，傳入 `CLAW_OLLAMA_BASE` 指向 fake Ollama
4. `tearDownClass` 用 `terminate()` + `wait(timeout=5)` 乾淨關閉 proxy、`shutdown()` 關 fake Ollama

### 本輪所做的強化（Strengthening）

在跑 v4 測試的同時，對 `local_ai/proxy.py` 做了以下 4 項修復，以符合「離線模式預設 zh-TW UTF-8」的設計目標：

| # | 位置 | 問題 | 修復 |
|---|------|------|------|
| S-v4-1 | `_send_json_error`（原版） | `json.dumps(..., ensure_ascii=True)` 導致中文錯誤訊息被跳脫成 `\uXXXX`，使用者在終端機看到亂碼 | 改為 `json.dumps(..., ensure_ascii=False).encode("utf-8")`，並補上 `Content-Type: application/json; charset=utf-8` 與精確的 `Content-Length` |
| S-v4-2 | 無法連線到 Ollama 的分支 | 英文錯誤 `Could not connect to Ollama` | 改為 `無法連線到 Ollama，請先執行 ollama serve` |
| S-v4-3 | 未知端點分支 | 英文 `Unknown endpoint: {path}` | 改為 `未知的端點：{path}` |
| S-v4-4 | JSON 解析失敗分支 | 英文 `Request body is not valid JSON` | 改為 `請求內容不是合法的 JSON` |

另外也順手把 `import os` 從某個 `finally` 區塊內拉到模組最上層（原本只在特定 code path 才會被 import，造成冷路徑測試時 `NameError`），並把上游 Ollama 呼叫強制 `stream=False`，由 proxy 自己決定要串流還是要等完整字串（C 修復流程必須拿到完整字串才能做靜態檢查）。

### 如何重跑 v4

```bash
cd ~/Desktop/research-claw-code
python3 tests/test_experimental_hardening_v4_proxy.py
```

不需 `pip install` 任何依賴——全程只用 Python 標準庫（`http.server`、`unittest`、`subprocess`、`socket`、`threading`、`json`）。

### 未納入本輪、建議後續補強的項目

以下是 v4 實驗中觀察到、但尚未寫成自動測試的潛在弱點，列給下一輪 v5 參考：

1. **SSE 斷線恢復：** 當下游 Ollama 中途斷線，目前 proxy 只會把錯誤包成一個 `message_delta`；沒有測試覆蓋「串到一半 upstream 500」的情境。
2. **C 修復無限迴圈保護：** `max_retries=2` 是靠計數器控制，沒有獨立測試驗證「即使模型連續 10 次回 C++，proxy 也必須在第 2 次之後停手」。
3. **超大 prompt 的 `Content-Length`：** 用 `len(body)` 應對中文 UTF-8 多位元組字元，可加一組 >1 MB body 的壓力測試。
4. **`CLAW_SYSTEM_PROMPT` 覆寫：** 環境變數注入的 system prompt 是否正確合流進上游 payload，目前只在 `run.sh` 的 smoke script 裡驗證，單元測試面沒有覆蓋。
5. **bundle manifest BOM-less 往返：** PowerShell 端的寫入已改成 `UTF8Encoding($false)`；建議加一組「Windows 寫、Linux 讀」的跨平台 fixture 測試。

這些項目建議排進 v5 計畫，暫不阻擋當前 v4 合入。

---

## 第五輪（v5）—— v4 建議補強點全數落實

**日期：** 2026-04-24
**新增測試數：** 12（累積 208）
**測試檔：** `tests/test_experimental_hardening_v5_proxy.py`
**執行指令：** `python3 tests/test_experimental_hardening_v5_proxy.py`
**執行結果：** `Ran 12 tests in 3.167s — OK` ✅
**目標：** 把 v4 結尾列出的 5 個 follow-up 項目逐一落實成自動化測試，並補上一項 proxy 的 SSE 復原強化。

### 背景

v4 結束時在 `TEST_RECORD.md` 留下 5 個建議補強點。v5 把每一項都寫成回歸測試，並在發現真實 bug 的地方直接修 proxy。重點發現是：當使用者送出 `stream=True` 請求但 Ollama 連線中途掉線時，proxy 原本已經送出 `HTTP 200 + text/event-stream` header，再從外層 `except URLError` 改丟 502 會形成「半份 SSE + 半份 JSON」的混亂回應。v5 把送 header 的時機延後到上游 stream 真的打開之後，並補一份 `_mid_stream_error_trailer` 專門處理「header 已送、上游才掛掉」的情境。

### 假設表格（Hypothesis Table）

| # | 假設 | 測試情境 | 預期 | 實際 | 狀態 |
|---|------|---------|------|------|------|
| H-v5-01 | `_mid_stream_error_trailer` 內含 `stop_reason=error` 與中文 UTF-8 錯誤文字 | 直接呼叫 helper 取 bytes | 包含 `message_delta`、`stop_reason`=error、中文字元原樣 | 全符合 | ✅ PASS |
| H-v5-02 | trailer 最後一個 event 必為 `message_stop` | 同上 | 末尾 event name = `message_stop` | 正確 | ✅ PASS |
| H-v5-03 | `stream=True` 且 upstream 連不上 → 502 + zh-TW JSON，不漏出半份 SSE | 起 proxy 指向死 port | HTTPError 502 + 「無法連線到 Ollama」 | 正確 | ✅ PASS |
| H-v5-04 | 非串流同樣回 502（回歸保護） | 相同 proxy，stream=False | HTTPError 502 + zh-TW | 正確 | ✅ PASS |
| H-v5-05 | 假 Ollama 每次都回 C++，proxy 最多打 `1 + MAX_C_REPAIR_ATTEMPTS` 次 | 單次 C 題請求 | `count == 3`（初次 + 2 重試） | `== 3` | ✅ PASS |
| H-v5-06 | 連續兩次 C 題請求的重試計數器互相獨立 | 呼叫兩次再看 delta | 第二次 delta 也是 3 | delta = 3 | ✅ PASS |
| H-v5-07 | 中文 JSON 錯誤 body 的 Content-Length 以位元組計而非字元 | 2000 中文字符測試 | `len(body) >= 6000` | `>= 6000` | ✅ PASS |
| H-v5-08 | ≈510 KB 的中文 prompt 可完整往返 proxy → Ollama → 回覆 | 170 000 中文字 × 3 bytes | Echo handler 回報 >= 170 000 字元 | 一致 | ✅ PASS |
| H-v5-09 | CLI `--system-prompt SENTINEL` 注入的 sentinel 會出現在上游 `system` 訊息 | 子行程啟動 proxy + RecordingHandler | system message 含 SENTINEL | 含 | ✅ PASS |
| H-v5-10 | sentinel 不會被誤當作 user message（泄漏保護） | 同上 payload | user messages 無 sentinel | 無 | ✅ PASS |
| H-v5-11 | BOM-less UTF-8 manifest 不以 `\xEF\xBB\xBF` 開頭 | 寫入 4 行含中文、讀 bytes | 無 BOM | 無 | ✅ PASS |
| H-v5-12 | 反面對照：若寫 BOM 則第一行開頭含 `U+FEFF`（確保測試本身有鑑別力） | 主動寫 BOM | 第一行以 BOM 開頭 | 正確 | ✅ PASS |

### 測試類別分佈

| 測試類別 | 測試數 | 覆蓋範圍 |
|---------|-------|---------|
| `TestMidStreamErrorTrailer` | 2 | SSE trailer 結構與 UTF-8 中文保真 |
| `UnreachableUpstreamProxy` | 2 | upstream 死掉時 stream/non-stream 都回 502 |
| `TestCRepairMaxRetries` | 2 | C 修復呼叫次數上限與跨請求獨立性 |
| `TestSendJsonErrorByteLength` | 1 | 多位元組 UTF-8 Content-Length |
| `TestLargeBodyRoundTrip` | 1 | ≈510 KB prompt 完整往返 |
| `TestSystemPromptPropagation` | 2 | `--system-prompt` CLI → 上游 system message |
| `TestBundleManifestBomless` | 2 | bundle manifest BOM-less 與對照組 |

### 本輪所做的強化（Strengthening）

| # | 位置 | 問題 | 修復 |
|---|------|------|------|
| S-v5-1 | `local_ai/proxy.py::_stream_response` | 舊版在 `send_response(200)` 之後才呼叫 `_open_ollama_stream()`；若上游打不通，`_handle_messages` 的 outer `except URLError` 會再嘗試送 502 JSON，導致「半份 SSE header + 半份 JSON body」的協定衝突。 | 把 `send_response(200)` 延後到 `_open_ollama_stream()` 成功之後；若上游打不開，exception 正常 bubble 到 `_handle_messages` 只送 JSON 錯誤。c-repair 路徑同樣改為「先取完整文字再 commit SSE header」。 |
| S-v5-2 | `local_ai/proxy.py::_stream_response` | 串流中途 upstream 掉線時，只會因為 `BrokenPipeError` 被靜默吞掉，客戶端看到 SSE 訊號沒有終止標記，UI 會卡在「回答中」。 | 新增 `_mid_stream_error_trailer()` helper；`URLError` / `HTTPError` / `http.client.IncompleteRead` / `ConnectionError` / `OSError` 被中途拋出時，送一份「errored `message_delta` + `message_stop`」trailer，讓客戶端乾淨收尾。 |
| S-v5-3 | `local_ai/proxy.py` import 區 | 之前缺 `http.client` 這一層 exception 類別。 | 在檔案頂端加上 `import http.client`。 |

### 端到端骨架

v5 測試混用兩種執行方式：

1. **In-process HTTPServer + `proxy.ProxyHandler`** —— 快速、可直接讀 handler 類別屬性，用來測 `UnreachableUpstreamProxy`、`TestCRepairMaxRetries`、`TestLargeBodyRoundTrip`。這些測試需要改寫 `ProxyHandler.ollama_url` 等屬性，in-process 最直接。
2. **子行程 `proxy.py --system-prompt ...`** —— 走真實 CLI 旗標路徑。`TestSystemPromptPropagation` 用這條驗證 `--system-prompt` CLI 旗標真的會把字串塞進上游 `system` message；用 `RecordingHandler.last_payload` 捕捉最後一次收到的 payload 做斷言。

兩種測試都用 `_pick_free_port()` 選空閒 port，避免和機器上其他服務衝突。子行程用 `_wait_for_health()` 輪詢 `/health` 直到 200 OK 才進入主要 assertions。

### 如何重跑 v5

```bash
cd ~/Desktop/research-claw-code
python3 tests/test_experimental_hardening_v5_proxy.py
```

合併重跑 v4 + v5：

```bash
python3 tests/test_experimental_hardening_v4_proxy.py && \
python3 tests/test_experimental_hardening_v5_proxy.py
```

預期：`Ran 22 tests in ~0.6s — OK` + `Ran 12 tests in ~3.2s — OK`。

### v4 五項建議的落實對照

| v4 遺留項目 | 對應 v5 測試 | 狀態 |
|------------|-------------|------|
| 1. SSE 斷線恢復 | H-v5-01/02 `_mid_stream_error_trailer`、H-v5-03/04 `UnreachableUpstreamProxy` | ✅ 落實 + 已強化 `_stream_response` |
| 2. C 修復無限迴圈保護 | H-v5-05/06 `TestCRepairMaxRetries` | ✅ 落實 |
| 3. 超大 prompt Content-Length | H-v5-07 `TestSendJsonErrorByteLength`、H-v5-08 `TestLargeBodyRoundTrip` | ✅ 落實 |
| 4. `CLAW_SYSTEM_PROMPT` 覆寫 | H-v5-09/10 `TestSystemPromptPropagation` | ✅ 落實（走 CLI 子行程路徑） |
| 5. bundle manifest BOM-less | H-v5-11/12 `TestBundleManifestBomless` | ✅ 落實（含反面對照組） |

### 下一輪（v6）可考慮的題目

v5 收尾時觀察到、但尚未立刻處理的事項：

1. **chunked transfer-encoding 行為：** 目前 `_stream_response` 靠 `self.wfile` 直接寫 bytes + `Cache-Control: no-cache`，並未明確設定 `Transfer-Encoding`；部分反向代理（nginx 預設）可能會把沒有 `Content-Length` 的 response 整份緩衝後才送出，導致 SSE 變批次輸出。建議補一個 `X-Accel-Buffering: no` header 並加測試。
2. **`_repair_c_response` 的 timeout 組合：** 每次 `_request_ollama_completion` 都是 120 秒 timeout；若模型連續三次都慢，使用者可能等到 6 分鐘才收到「還是不對」的回覆。可加一個「總 wallclock 上限」機制。
3. **`text_to_anthropic_sse` 的單字斷詞：** 目前用 `text.split()` 估 output_tokens，對純中文會永遠回 1；若需要更準確的 token 計數可接上 `tiktoken` 或改用 ollama 回報的 eval_count。
4. **`FUNCTION_DEF_PATTERN` 的 regex 覆蓋率：** 目前沒有定義 `int *` 指標回傳型別的函式，也沒有 `const` 修飾；在複雜 C 題可能誤報 unresolved call。建議補幾筆 edge case。

這些不是 bug，只是未來想要更紮實時的 follow-up。
