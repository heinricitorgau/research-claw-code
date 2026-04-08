# 對齊狀態 — claw-code Rust Port

最後更新：2026-04-03

## 摘要

- Canonical 文件：這份最上層的 `PARITY.md` 是 `rust/scripts/run_mock_parity_diff.py` 所消費的檔案。
- 要求的 9-lane checkpoint：**9 條 lanes 全部已合併到 `main`。**
- 目前 `main` HEAD：`ee31e00`（stub implementations 已被真實的 AskUserQuestion + RemoteTrigger 取代）。
- 這個 checkpoint 下的 repository 統計：`main` 上 **292 commits** / 所有 branches 合計 **293 commits**、**9 個 crates**、**48,599 行受追蹤 Rust LOC**、**2,568 行測試 LOC**、**3 位作者**，日期範圍 **2026-03-31 → 2026-04-03**。
- Mock parity harness 統計：**10 個 scripted scenarios**、在 `rust/crates/rusty-claude-cli/tests/mock_parity_harness.rs` 中捕捉到 **19 個 `/v1/messages` requests**。

## Mock parity harness — 里程碑 1

- [x] 可決定性的、相容 Anthropic 的 mock service（`rust/crates/mock-anthropic-service`）
- [x] 可重現、乾淨環境的 CLI harness（`rust/crates/rusty-claude-cli/tests/mock_parity_harness.rs`）
- [x] Scripted scenarios：`streaming_text`、`read_file_roundtrip`、`grep_chunk_assembly`、`write_file_allowed`、`write_file_denied`

## Mock parity harness — 里程碑 2（行為擴充）

- [x] Scripted multi-tool turn coverage：`multi_tool_turn_roundtrip`
- [x] Scripted bash coverage：`bash_stdout_roundtrip`
- [x] Scripted permission prompt coverage：`bash_permission_prompt_approved`、`bash_permission_prompt_denied`
- [x] Scripted plugin-path coverage：`plugin_tool_roundtrip`
- [x] Behavioral diff/checklist runner：`rust/scripts/run_mock_parity_diff.py`

## Harness v2 行為檢查清單

Canonical scenario map：`rust/mock_parity_scenarios.json`

- Multi-tool assistant turns
- Bash flow roundtrips
- Permission enforcement across tool paths
- Plugin tool execution path
- File tools — harness 驗證過的 flows
- 由 mock parity harness 驗證的 streaming response support

## 9-lane checkpoint

| Lane | 狀態 | Feature commit | Merge commit | 證據 |
|---|---|---|---|---|
| 1. Bash validation | merged | `36dac6c` | `1cfd78a` | `jobdori/bash-validation-submodules`, `rust/crates/runtime/src/bash_validation.rs`（在 `main` 上 `+1004`） |
| 2. CI fix | merged | `89104eb` | `f1969ce` | `rust/crates/runtime/src/sandbox.rs`（`+22/-1`） |
| 3. File-tool | merged | `284163b` | `a98f2b6` | `rust/crates/runtime/src/file_ops.rs`（`+195/-1`） |
| 4. TaskRegistry | merged | `5ea138e` | `21a1e1d` | `rust/crates/runtime/src/task_registry.rs`（`+336`） |
| 5. Task wiring | merged | `e8692e4` | `d994be6` | `rust/crates/tools/src/lib.rs`（`+79/-35`） |
| 6. Team+Cron | merged | `c486ca6` | `49653fe` | `rust/crates/runtime/src/team_cron_registry.rs`, `rust/crates/tools/src/lib.rs`（`+441/-37`） |
| 7. MCP lifecycle | merged | `730667f` | `cc0f92e` | `rust/crates/runtime/src/mcp_tool_bridge.rs`, `rust/crates/tools/src/lib.rs`（`+491/-24`） |
| 8. LSP client | merged | `2d66503` | `d7f0dc6` | `rust/crates/runtime/src/lsp_client.rs`, `rust/crates/tools/src/lib.rs`（`+461/-9`） |
| 9. Permission enforcement | merged | `66283f4` | `336f820` | `rust/crates/runtime/src/permission_enforcer.rs`, `rust/crates/tools/src/lib.rs`（`+357`） |

## Lane 細節

### Lane 1 — Bash validation

- **狀態：** 已合併到 `main`。
- **Feature commit：** `36dac6c` — `feat: add bash validation submodules — readOnlyValidation, destructiveCommandWarning, modeValidation, sedValidation, pathValidation, commandSemantics`
- **證據：** branch-only diff 新增 `rust/crates/runtime/src/bash_validation.rs` 與一個 `runtime::lib` export（2 個檔案共 `+1005`）。
- **`main` branch 的實際情況：** `rust/crates/runtime/src/bash.rs` 仍是 `main` 上啟用中的實作，長度 **283 LOC**，含 timeout/background/sandbox execution。`PermissionEnforcer::check_bash()` 在 `main` 上加入了 read-only gating，但專用 validation module 尚未落地。

### Bash tool — upstream 有 18 個 submodules，Rust 目前有 1 個

- 在 `main` 上，這個說法本質上仍然成立。
- Harness coverage 已證明 bash execution 與 prompt escalation flows，但尚未覆蓋完整 upstream validation matrix。
- 這條 branch-only lane 的目標是 `readOnlyValidation`、`destructiveCommandWarning`、`modeValidation`、`sedValidation`、`pathValidation` 與 `commandSemantics`。

### Lane 2 — CI fix

- **狀態：** 已合併到 `main`。
- **Feature commit：** `89104eb` — `fix(sandbox): probe unshare capability instead of binary existence`
- **Merge commit：** `f1969ce` — `Merge jobdori/fix-ci-sandbox: probe unshare capability for CI fix`
- **證據：** `rust/crates/runtime/src/sandbox.rs` 長度為 **385 LOC**，現在會根據真實 `unshare` capability 與 container signals 判斷 sandbox support，而不是只因為 binary 存在就假設支援。
- **重要性：** `.github/workflows/rust-ci.yml` 會執行 `cargo fmt --all --check` 與 `cargo test -p rusty-claude-cli`；這條 lane 消除了 runtime behavior 中只在 CI 會出現的 sandbox 假設。

### Lane 3 — File-tool

- **狀態：** 已合併到 `main`。
- **Feature commit：** `284163b` — `feat(file_ops): add edge-case guards — binary detection, size limits, workspace boundary, symlink escape`
- **Merge commit：** `a98f2b6` — `Merge jobdori/file-tool-edge-cases: binary detection, size limits, workspace boundary guards`
- **證據：** `rust/crates/runtime/src/file_ops.rs` 長度為 **744 LOC**，目前已包含 `MAX_READ_SIZE`、`MAX_WRITE_SIZE`、NUL-byte binary detection，以及 canonical workspace-boundary validation。
- **Harness coverage：** `read_file_roundtrip`、`grep_chunk_assembly`、`write_file_allowed` 與 `write_file_denied` 都已在 manifest 中定義，並由 clean-env harness 實際執行。

### File tools — 經 harness 驗證的 flows

- `read_file_roundtrip` 驗證 read-path execution 與最終 synthesis。
- `grep_chunk_assembly` 驗證 chunked grep tool output handling。
- `write_file_allowed` 與 `write_file_denied` 同時驗證 write success 與 permission denial。

### Lane 4 — TaskRegistry

- **狀態：** 已合併到 `main`。
- **Feature commit：** `5ea138e` — `feat(runtime): add TaskRegistry — in-memory task lifecycle management`
- **Merge commit：** `21a1e1d` — `Merge jobdori/task-runtime: TaskRegistry in-memory lifecycle management`
- **證據：** `rust/crates/runtime/src/task_registry.rs` 長度為 **335 LOC**，提供 thread-safe in-memory registry，具備 `create`、`get`、`list`、`stop`、`update`、`output`、`append_output`、`set_status` 與 `assign_team`。
- **範圍：** 這條 lane 以真實 runtime-backed task records 取代原本固定 payload 的 stub state，但本身尚未加入 external subprocess execution。

### Lane 5 — Task wiring

- **狀態：** 已合併到 `main`。
- **Feature commit：** `e8692e4` — `feat(tools): wire TaskRegistry into task tool dispatch`
- **Merge commit：** `d994be6` — `Merge jobdori/task-registry-wiring: real TaskRegistry backing for all 6 task tools`
- **證據：** `rust/crates/tools/src/lib.rs` 目前透過 `execute_tool()` 與具體的 `run_task_*` handlers，分派 `TaskCreate`、`TaskGet`、`TaskList`、`TaskStop`、`TaskUpdate` 與 `TaskOutput`。
- **目前狀態：** task tools 現在已透過 `global_task_registry()` 在 `main` 上暴露真實的 registry state。

### Lane 6 — Team+Cron

- **狀態：** 已合併到 `main`。
- **Feature commit：** `c486ca6` — `feat(runtime+tools): TeamRegistry and CronRegistry — replace team/cron stubs`
- **Merge commit：** `49653fe` — `Merge jobdori/team-cron-runtime: TeamRegistry + CronRegistry wired into tool dispatch`
- **證據：** `rust/crates/runtime/src/team_cron_registry.rs` 長度為 **363 LOC**，新增 thread-safe 的 `TeamRegistry` 與 `CronRegistry`；`rust/crates/tools/src/lib.rs` 也將 `TeamCreate`、`TeamDelete`、`CronCreate`、`CronDelete` 與 `CronList` 接到這些 registries。
- **目前狀態：** team/cron tools 在 `main` 上已具備 in-memory lifecycle behavior；但仍未進到真實 background scheduler 或 worker fleet 層級。

### Lane 7 — MCP lifecycle

- **狀態：** 已合併到 `main`。
- **Feature commit：** `730667f` — `feat(runtime+tools): McpToolRegistry — MCP lifecycle bridge for tool surface`
- **Merge commit：** `cc0f92e` — `Merge jobdori/mcp-lifecycle: McpToolRegistry lifecycle bridge for all MCP tools`
- **證據：** `rust/crates/runtime/src/mcp_tool_bridge.rs` 長度為 **406 LOC**，目前可追蹤 server connection status、resource listing、resource reads、tool listing、tool dispatch acknowledgements、auth state 與 disconnects。
- **接線情況：** `rust/crates/tools/src/lib.rs` 目前已將 `ListMcpResources`、`ReadMcpResource`、`McpAuth` 與 `MCP` 路由到 `global_mcp_registry()` handlers。
- **範圍：** 這條 lane 在 `main` 上以 registry bridge 取代了純 stub responses；但 end-to-end MCP connection population 與更廣泛的 transport/runtime 深度，仍取決於更完整的 MCP runtime（`mcp_stdio.rs`、`mcp_client.rs`、`mcp.rs`）。

### Lane 8 — LSP client

- **狀態：** 已合併到 `main`。
- **Feature commit：** `2d66503` — `feat(runtime+tools): LspRegistry — LSP client dispatch for tool surface`
- **Merge commit：** `d7f0dc6` — `Merge jobdori/lsp-client: LspRegistry dispatch for all LSP tool actions`
- **證據：** `rust/crates/runtime/src/lsp_client.rs` 長度為 **438 LOC**，可在 stateful registry 中建模 diagnostics、hover、definition、references、completion、symbols 與 formatting。
- **接線情況：** `rust/crates/tools/src/lib.rs` 目前暴露的 `LSP` tool schema 已列出 `symbols`、`references`、`diagnostics`、`definition` 與 `hover`，並將 requests 透過 `registry.dispatch(action, path, line, character, query)` 路由。
- **範圍：** 目前的 parity 仍停留在 registry/dispatch 層級；completion/format 雖存在於 registry model 中，但尚未同樣清楚地暴露在 tool schema 邊界，而且真實外部 language-server process orchestration 仍是另一條獨立工作。

### Lane 9 — Permission enforcement

- **狀態：** 已合併到 `main`。
- **Feature commit：** `66283f4` — `feat(runtime+tools): PermissionEnforcer — permission mode enforcement layer`
- **Merge commit：** `336f820` — `Merge jobdori/permission-enforcement: PermissionEnforcer with workspace + bash enforcement`
- **證據：** `rust/crates/runtime/src/permission_enforcer.rs` 長度為 **340 LOC**，在 `rust/crates/runtime/src/permissions.rs` 之上新增 tool gating、file write boundary checks，以及 bash read-only heuristics。
- **接線情況：** `rust/crates/tools/src/lib.rs` 已暴露 `enforce_permission_check()`，並在 tool specs 中攜帶每個 tool 的 `required_permission`。

### 跨 tool paths 的 permission enforcement

- Harness scenarios 已驗證 `write_file_denied`、`bash_permission_prompt_approved` 與 `bash_permission_prompt_denied`。
- `PermissionEnforcer::check()` 會委派給 `PermissionPolicy::authorize()`，並回傳結構化的 allow/deny 結果。
- `check_file_write()` 會強制 workspace boundaries 與 read-only denial；`check_bash()` 則會在 read-only mode 下拒絕 mutating commands，並阻擋未確認的 prompt-mode bash。

## Tool Surface：`main` 上暴露 40 個 tool specs

- `mvp_tool_specs()` 在 `rust/crates/tools/src/lib.rs` 中暴露 **40** 個 tool specs。
- 核心 execution 已存在於 `bash`、`read_file`、`write_file`、`edit_file`、`glob_search` 與 `grep_search`。
- `mvp_tool_specs()` 中現有的 product tools 包含 `WebFetch`、`WebSearch`、`TodoWrite`、`Skill`、`Agent`、`ToolSearch`、`NotebookEdit`、`Sleep`、`SendUserMessage`、`Config`、`EnterPlanMode`、`ExitPlanMode`、`StructuredOutput`、`REPL` 與 `PowerShell`。
- 這次 9-lane 推進，已在 `main` 上以 registry-backed handlers 取代 `Task*`、`Team*`、`Cron*`、`LSP` 與 MCP tools 原本純 fixed-payload stubs。
- `Brief` 在 `execute_tool()` 中作為 execution alias 處理，但它並不是 `mvp_tool_specs()` 中獨立暴露的 tool spec。

### 仍然受限或刻意保持淺層的部分

- `AskUserQuestion` 目前仍只回傳 pending response payload，而非真實 interactive UI wiring。
- `RemoteTrigger` 仍是 stub response。
- `TestingPermission` 仍僅用於測試。
- Task、team、cron、MCP 與 LSP 已不再只是 `execute_tool()` 中的 fixed-payload stubs，但其中數個仍是 registry-backed approximations，而非完整 external-runtime integrations。
- Bash 深層 validation 在 `36dac6c` 合併前仍只存在 branch 中。

## 與舊版 PARITY 檢查清單的對齊結果

- [x] Path traversal prevention（包含 symlink following 與 `../` escapes）
- [x] Size limits on read/write
- [x] Binary file detection
- [x] Permission mode enforcement（read-only vs workspace-write）
- [x] Config merge precedence（user > project > local）— `ConfigLoader::discover()` 目前會按 user → project → local 載入，而 `loads_and_merges_claude_code_config_files_by_precedence()` 已驗證 merge order。
- [x] Plugin install/enable/disable/uninstall flow — `rust/crates/commands/src/lib.rs` 中的 `/plugin` slash handling 會委派到 `rust/crates/plugins/src/lib.rs` 的 `PluginManager::{install, enable, disable, uninstall}`。
- [x] 沒有 `#[ignore]` tests 把 failures 藏起來 — 對 `rust/**/*.rs` 做 `grep` 後，找到 0 個 ignored tests。

## 仍待完成

- [ ] 超越目前 registry bridge 的 end-to-end MCP runtime lifecycle
- [x] Output truncation（large stdout/file content）
- [ ] Session compaction behavior matching
- [ ] Token counting / cost tracking accuracy
- [x] Bash validation lane 已合併到 `main`
- [ ] 每個 commit 的 CI 都是綠的

## Migration Readiness

- [x] `PARITY.md` 維護中，且內容誠實
- [x] 9 條要求的 lanes 都有 commit hashes 與 current status 文件化
- [x] 9 條要求的 lanes 都已落地到 `main`（`bash-validation` 仍是 branch-only）
- [x] 沒有 `#[ignore]` tests 藏 failure
- [ ] 每個 commit 的 CI 都是綠的
- [x] Codebase shape 足夠乾淨，可交付 handoff documentation
