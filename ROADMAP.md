# ROADMAP.md

# Clawable Coding Harness 路線圖

## 目標

把 claw-code 變成最 **clawable** 的 coding harness：

- 不假設人類優先的 terminal 使用方式
- 不依賴脆弱的 prompt 注入時機
- 不容許 opaque 的 session state
- 不隱藏 plugin 或 MCP failures
- 不需要人類替例行 recovery 持續 babysitting

這份 roadmap 的前提是：主要使用者是**透過 hooks、plugins、sessions 與 channel events 接線進來的 claws**。

## 「clawable」的定義

一個 clawable harness 應該具備：

- 可決定性地啟動
- 狀態與 failure modes 可被機器讀取
- 不需要人類盯著 terminal 也能恢復
- 知道 branch / test / worktree 狀態
- 知道 plugin / MCP lifecycle 狀態
- 以 event 為先，而不是以 log 為先
- 能夠自主執行下一步

## 當前痛點

### 1. Session 啟動仍然脆弱
- trust prompts 可能阻塞 TUI 啟動
- prompt 可能落進 shell，而不是 coding agent
- 「session exists」不等於「session is ready」

### 2. 真實狀態散落在多層之間
- tmux state
- clawhip event stream
- git/worktree state
- test state
- gateway/plugin/MCP runtime state

### 3. Events 太像 logs
- claws 目前仍必須從 noisy text 中推斷太多事情
- 關鍵狀態尚未被正規化為 machine-readable events

### 4. Recovery loops 太依賴人工
- restart worker
- 接受 trust prompt
- 重新注入 prompt
- 偵測 stale branch
- retry failed startup
- 手動區分 infra vs code failures

### 5. Branch freshness 還不夠被強制
- side branches 可能漏掉 main 上已經落地的 fixes
- 大範圍測試失敗有時只是 stale branch 雜訊，不是真回歸

### 6. Plugin/MCP failures 分類不足
- startup failures、handshake failures、config errors、partial startup 與 degraded mode 還沒有被足夠清楚地暴露出來

### 7. 人類 UX 仍滲入 claw workflows
- 太多流程仍依賴 terminal/TUI 行為，而不是明確的 agent state transitions 與 control APIs

## 產品原則

1. **State machine first**：每個 worker 都要有明確 lifecycle states。
2. **Events over scraped prose**：channel output 應由 typed events 推導，而不是由抓取文字湊出來。
3. **Recovery before escalation**：已知 failure modes 應先自動修復一次，再決定是否求助。
4. **Branch freshness before blame**：先檢查 stale branch，再把紅測試當成新 regression。
5. **Partial success is first-class**：例如 MCP startup 可以部分成功、部分失敗，且需有結構化 degraded-mode reporting。
6. **Terminal is transport, not truth**：tmux/TUI 可以保留成實作細節，但 orchestration state 必須活在更高一層。
7. **Policy is executable**：merge、retry、rebase、stale cleanup 與 escalation rules 應由機器執行，而不是只存在聊天指令裡。

## 路線圖

## Phase 1 — Reliable Worker Boot

### 1. Coding workers 的 ready-handshake lifecycle
新增明確狀態：

- `spawning`
- `trust_required`
- `ready_for_prompt`
- `prompt_accepted`
- `running`
- `blocked`
- `finished`
- `failed`

驗收標準：

- 在 `ready_for_prompt` 前永遠不送 prompt
- 可以偵測並發出 trust prompt state
- shell 誤投遞成為可偵測的一級 failure state

### 2. Trust prompt resolver
為已知 repos/worktrees 增加 allowlisted auto-trust 行為。

驗收標準：

- trusted repos 會自動清除 trust prompts
- 發出 `trust_required` 與 `trust_resolved` events
- 不在 allowlist 中的 repos 仍保留 gating

### 3. Structured session control API
在 tmux 之上提供機器控制介面：

- create worker
- await ready
- send task
- fetch state
- fetch last error
- restart worker
- terminate worker

驗收標準：

- claw 可以在不依賴 raw send-keys 的情況下操作 coding worker

## Phase 2 — Event-Native Clawhip Integration

### 4. Canonical lane event schema
定義 typed events，例如：

- `lane.started`
- `lane.ready`
- `lane.prompt_misdelivery`
- `lane.blocked`
- `lane.red`
- `lane.green`
- `lane.commit.created`
- `lane.pr.opened`
- `lane.merge.ready`
- `lane.finished`
- `lane.failed`
- `branch.stale_against_main`

驗收標準：

- clawhip 能消費 typed lane events
- Discord summaries 由 structured events 渲染，而不是只靠 pane scraping

### 5. Failure taxonomy
正規化 failure classes：

- `prompt_delivery`
- `trust_gate`
- `branch_divergence`
- `compile`
- `test`
- `plugin_startup`
- `mcp_startup`
- `mcp_handshake`
- `gateway_routing`
- `tool_runtime`
- `infra`

驗收標準：

- blockers 能被機器分類
- dashboards 與 retry policies 可依 failure type 分流

### 6. Actionable summary compression
把 noisy event streams 壓縮成：

- current phase
- last successful checkpoint
- current blocker
- recommended next recovery action

驗收標準：

- channel status updates 保持精簡且 machine-grounded
- claws 不再需要從 raw build spam 猜狀態

## Phase 3 — Branch/Test Awareness and Auto-Recovery

### 7. 在大範圍驗證前先做 stale-branch detection
在跑 broad tests 前，先比較目前 branch 與 `main`，確認是否缺少已知 fixes。

驗收標準：

- 發出 `branch.stale_against_main`
- 依 policy 建議或自動執行 rebase/merge-forward
- 避免把 stale-branch failures 誤判成新的 regressions

### 8. 常見 failures 的 recovery recipes
把已知自動修復流程編碼化，涵蓋：

- trust prompt unresolved
- prompt 被送進 shell
- stale branch
- cross-crate refactor 後 compile red
- MCP startup handshake failure
- partial plugin startup

驗收標準：

- 在 escalation 前先自動恢復一次
- recovery attempt 本身也要發出 structured event data

### 9. Green-ness contract
workers 應能區分：

- targeted tests green
- package green
- workspace green
- merge-ready green

驗收標準：

- 不再出現模糊的「tests passed」訊息
- merge policy 可以依 lane type 要求正確層級的 green

## Phase 4 — Claws-First Task Execution

### 10. Typed task packet format
定義結構化 task packet，欄位例如：

- objective
- scope
- repo/worktree
- branch policy
- acceptance tests
- commit policy
- reporting contract
- escalation policy

驗收標準：

- claws 可不只依賴長篇自然語言 prompt blobs 來派工
- task packets 可被安全記錄、重試與轉換

### 11. Autonomous coding 的 policy engine
把自動化規則編碼化，例如：

- 若 green + scoped diff + review passed -> merge to dev
- 若 stale branch -> 先 merge-forward 再做 broad tests
- 若 startup blocked -> recover once, then escalate
- 若 lane completed -> emit closeout and cleanup session

驗收標準：

- doctrine 從 chat instructions 進一步轉成 executable rules

### 12. Claw-native dashboards / lane board
暴露 machine-readable board，顯示：

- repos
- active claws
- worktrees
- branch freshness
- red/green state
- current blocker
- merge readiness
- last meaningful event

驗收標準：

- claws 可直接查詢狀態
- human-facing views 只是 rendering layer，不再是 source of truth

## Phase 5 — Plugin and MCP Lifecycle Maturity

### 13. First-class plugin/MCP lifecycle contract
每個 plugin/MCP integration 都應暴露：

- config validation contract
- startup healthcheck
- discovery result
- degraded-mode behavior
- shutdown/cleanup contract

驗收標準：

- partial-startup 與 per-server failures 以結構化方式回報
- 即使有一個 server 失敗，其餘成功的 servers 仍可使用

### 14. MCP end-to-end lifecycle parity
補齊以下面向的差距：

- config load
- server registration
- spawn/connect
- initialize handshake
- tool/resource discovery
- invocation path
- error surfacing
- shutdown/cleanup

驗收標準：

- parity harness 與 runtime tests 可涵蓋 healthy 與 degraded startup cases
- 壞掉的 servers 會以 structured failures 呈現，而不是 opaque warnings

## Immediate Backlog（來自當前真實痛點）

優先順序：P0 = 阻塞 CI/green state，P1 = 阻塞 integration wiring，P2 = clawability hardening，P3 = swarm-efficiency improvements。

**P0 — 優先修復（CI reliability）**
1. 把 `render_diff_report` tests 隔離到 tmpdir — **完成**：`render_diff_report_for()` tests 現在在 temp git repos 中執行，而不是 live working tree；定向 `cargo test -p rusty-claude-cli render_diff_report -- --nocapture` 在 branch/worktree 活動下仍保持綠燈
2. 將 GitHub CI 從單 crate 覆蓋擴大為 workspace 級驗證 — **完成**：`.github/workflows/rust-ci.yml` 現在在 workspace 層級執行 `cargo test --workspace`、fmt 與 clippy
3. 新增 release-grade binary workflow — **完成**：`.github/workflows/release.yml` 現在會為 CLI 建置 tagged Rust release artifacts
4. 新增 container-first 測試/執行文件 — **完成**：`Containerfile` + `docs/container.md` 文件化 canonical Docker/Podman workflow，用於 build、bind-mount 與 `cargo test --workspace`
5. 在 onboarding docs 與 help 中凸顯 `doctor` / preflight diagnostics — **完成**：README + USAGE 現在把 `claw doctor` / `/doctor` 放在 first-run path，並指向 built-in preflight report
6. 在 CI 自動化 branding/source-of-truth residue checks — **完成**：`.github/scripts/check_doc_source_of_truth.py` 與 `doc-source-of-truth` CI job 現在會阻擋 tracked docs 與 metadata 中過期的 repo/org/invite residue
7. 消除首次執行 help/build path 的 warning spam — **完成**：目前 `cargo run -q -p rusty-claude-cli -- --help` 可以直接輸出乾淨 help，不再先出現一整牆 warnings
8. 把 `doctor` 從 slash-only 提升為 top-level CLI entrypoint — **完成**：`claw doctor` 現在可直接由 local shell 執行，且有 direct help 與 health-report output 的 regression coverage
9. 讓 machine-readable status commands 真正 machine-readable — **完成**：`claw --output-format json status` 與 `claw --output-format json sandbox` 現在輸出 structured JSON snapshots，而不是 prose tables
10. 在 user-facing output 中統一 legacy config/skill namespaces — **完成**：skills/help JSON/text output 現在把 `.claw` 作為 canonical namespace，並把 legacy roots 收斂到 `.claw` 風格的 source ids/labels
11. 讓 `skills` 與 `mcp` 這類 inventory commands 尊重 JSON output — **完成**：direct CLI inventory commands 現在會尊重 `--output-format json`，為 skills 與 MCP inventory 輸出 structured payloads
12. 稽核整個 CLI surface 的 `--output-format` contract — **完成**：direct CLI commands 現在在 help/version/status/sandbox/agents/mcp/skills/bootstrap-plan/system-prompt/init/doctor 之間都遵守 deterministic JSON/text handling，並在 `output_format_contract.rs` 與 resumed `/status` JSON coverage 中有 regression coverage

**P1 — 接下來（integration wiring，解除 verification 阻塞）**
2. 新增跨模組 integration tests — **完成**：已有 12 個 integration tests，涵蓋 worker→recovery→policy、stale_branch→policy、green_contract→policy、reconciliation flows
3. 接上 lane-completion emitter — **完成**：`lane_completion` module 與 `detect_lane_completion()` 會根據 session-finished + tests-green + push-complete，自動把 `LaneContext::completed` 設為完成並進入 policy closeout
4. 將 `SummaryCompressor` 接進 lane event pipeline — **完成**：`compress_summary_text()` 現在會餵給 `tools/src/lib.rs` 中 `LaneEvent::Finished` 的 detail field

**P2 — Clawability hardening（原始 backlog）**
5. Worker readiness handshake + trust resolution — **完成**：`WorkerStatus` state machine 已有 `Spawning` → `TrustRequired` → `ReadyForPrompt` → `PromptAccepted` → `Running` lifecycle，以及 `trust_auto_resolve` + `trust_gate_cleared` gating
6. Prompt misdelivery detection and recovery — **完成**：已有 `prompt_delivery_attempts` counter、`PromptMisdelivery` event detection、`auto_recover_prompt_misdelivery` + `replay_prompt` recovery arm
7. Canonical lane event schema in clawhip — **完成**：已有 `LaneEvent` enum 與 `Started/Blocked/Failed/Finished` variants、`LaneEvent::new()` typed constructor，以及 `tools/src/lib.rs` integration
8. Failure taxonomy + blocker normalization — **完成**：已有 `WorkerFailureKind` enum（`TrustGate/PromptDelivery/Protocol/Provider`）與 `FailureScenario::from_worker_failure_kind()` bridge to recovery recipes
9. 在 workspace tests 前做 stale-branch detection — **完成**：已有 `stale_branch.rs` module，提供 freshness detection、behind/ahead metrics 與 policy integration
10. MCP structured degraded-startup reporting — **完成**：`McpManager` 已支援 degraded-startup reporting（`mcp_stdio.rs` 中 +183 行），並提供 failed server classification（startup/handshake/config/partial）與 tool output 中結構化的 `failed_servers` + `recovery_recommendations`
11. Structured task packet format — **完成**：已有 `task_packet.rs` module、`TaskPacket` struct、validation、serialization、`TaskScope` resolution（workspace/module/single-file/custom），並整合進 `tools/src/lib.rs`
12. Lane board / machine-readable status API — **完成**：lane completion hardening + `LaneContext::completed` auto-detection + MCP degraded reporting 都已提供 machine-readable state
13. **Session completion failure classification** — **完成**：`WorkerFailureKind::Provider` + `observe_completion()` + recovery recipe bridge 已落地
14. **Config merge validation gap** — **完成**：`config.rs` 在 deep-merge 前增加 hook validation（+56 行）；格式錯誤的 entries 會帶著 source-path context 失敗，而不是以 merged parse errors 失敗
15. **MCP manager discovery flaky test** — **完成**：`manager_discovery_report_keeps_healthy_servers_when_one_server_fails` 經多次穩定通過後，已恢復為一般 workspace test，不再藏在 `#[ignore]` 後面
16. **Commit provenance / worktree-aware push events** — **完成**：`LaneCommitProvenance` 現在在 lane events 中帶 branch/worktree/canonical-commit/supersession metadata；`dedupe_superseded_commit_events()` 會在 agent manifests 寫出前去重，讓 superseded commit events 收斂到最新 canonical lineage
17. **Orphaned module integration audit** — **完成**：`runtime` 現在把 `session_control` 與 `trust_resolver` 放在 `#[cfg(test)]` 後面，直到它們接入真實非測試執行路徑，避免一般 builds 對外宣稱實際不存在的 clawability surface
18. **Context-window preflight gap** — **完成**：provider request sizing 現在會在 oversized requests 離開 process 前發出 `context_window_blocked`，並改用 model-context registry，而不是舊的 naive max-token heuristic
19. **Subcommand help falls through into runtime/API path** — **完成**：`claw doctor --help`、`claw status --help`、`claw sandbox --help`，以及巢狀 `mcp`/`skills` help 現在都可在本地攔截，不需啟動 runtime/provider，且有 regression tests 覆蓋 direct CLI paths
20. **Session state classification gap（working / blocked / finished / truly stale）** — **完成**：agent manifests 現在可推導 `working`、`blocked_background_job`、`blocked_merge_conflict`、`degraded_mcp`、`interrupted_transport`、`finished_pending_report`、`finished_cleanable` 等 machine states；terminal-state persistence 也會記錄 commit provenance 與 derived state，讓下游 monitoring 能區分安靜進展與真正閒置
21. **Resumed `/status` JSON parity gap** — dogfooding 顯示 fresh `claw status --output-format json` 已輸出 structured JSON，但 resumed slash-command status 在至少一條 dispatch path 中仍會漏回 text-shaped path。local CI-equivalent repro 在 `rust/crates/rusty-claude-cli/tests/resume_slash_commands.rs::resumed_status_command_emits_structured_json_when_requested` 失敗，錯誤為 `expected value at line 1 column 1`，因此 resumed 狀態輸出一致性仍待修補
22. **Worktree binding semantics** — sessions 預設會繼承 parent 的 workspace root；若要切到新 worktree，必須明確 re-bind，而且這個 re-bind 本身也應被記錄為 structured event，以便 orchestrator 稽核 cross-worktree handoffs  
    - 額外需要暴露 `branch.workspace_mismatch` lane event，讓 clawhip 不再把錯誤 CWD 下的寫入誤算為 lane completion  
    **目前狀態：** `Session` 已在 `rust/crates/runtime/src/session.rs` 中新增 `workspace_root` 欄位，並完成 builder、accessor、JSON + JSONL round-trip、fork inheritance，以及 `persists_workspace_root_round_trip_and_forks_inherit_it` 的 given/when/then test coverage。CWD validation、namespaced on-disk path 與 `branch.workspace_mismatch` lane event 仍待完成，並持續掛在這個項目下。

**P3 — Swarm efficiency**
13. Swarm branch-lock protocol — **完成**：`branch_lock::detect_branch_lock_collisions()` 現在能在 parallel lanes 漂移成重複實作前，先偵測 same-branch/same-scope 與 nested-module collisions
14. Commit provenance / worktree-aware push events — **完成**：lane event provenance 現在包含 branch/worktree/superseded/canonical lineage metadata；manifest persistence 也會在下游 consumers 渲染前先去除 superseded commit events

## 建議的 Session 拆分

### Session A — worker boot protocol
重點：

- trust prompt detection
- ready-for-prompt handshake
- prompt misdelivery detection

### Session B — clawhip lane events
重點：

- canonical lane event schema
- failure taxonomy
- summary compression

### Session C — branch/test intelligence
重點：

- stale-branch detection
- green-level contract
- recovery recipes

### Session D — MCP lifecycle hardening
重點：

- startup/handshake reliability
- structured failed server reporting
- degraded-mode runtime behavior
- lifecycle tests/harness coverage

### Session E — typed task packets + policy engine
重點：

- structured task format
- retry/merge/escalation rules
- autonomous lane closure behavior

## MVP 成功標準

當以下條件成立時，我們就可以認為 claw-code 在實質上變得更 clawable：

- claw 可以啟動 worker，且能確定它何時 ready
- claws 不再把 tasks 誤打到 shell 裡
- stale-branch failures 能在浪費除錯時間前先被辨識
- clawhip 回報 machine states，而不只是 tmux prose
- MCP/plugin startup failures 被清楚分類並暴露
- coding lane 能在不需要人工 babysitting 的情況下，自行從常見 startup 與 branch 問題恢復

## 短版結論

claw-code 應從：

- 一個人類也能操作的 CLI

演進為：

- 一個 **claw-native execution runtime**
- 一個 **event-native orchestration substrate**
- 一個 **plugin/hook-first autonomous coding harness**

## Deployment Architecture Gap（來自 2026-04-08 dogfood）

### WorkerState 在 runtime 中；但 `/state` 不在 opencode serve 中

**這是在 batch 8 dogfood 中發現的 root cause。**

`worker_boot.rs` 有一套完整的 `WorkerStatus` state machine（`Spawning → TrustRequired → ReadyForPrompt → Running → Finished/Failed`）。它也從 `runtime/src/lib.rs` 作為 public API 匯出。但 claw-code 是載入在 `opencode` binary 內部的 **plugin**，它無法替 `opencode serve` 新增 HTTP routes。HTTP server 完全由上游 `opencode` process（v1.3.15）擁有。

**影響：** 目前沒有辦法用 `curl localhost:4710/state` 直接拿到 JSON `WorkerStatus`。若要有這種 endpoint，必須符合下列其中一種方式：
1. 把 `/state` route upstream 到 opencode 的 HTTP server（需要對 `sst/opencode` 發 PR），或
2. 寫一個 sidecar HTTP process，在 process 內查詢 `WorkerRegistry`（可行，但脆弱），或
3. 把 `WorkerStatus` 寫到固定檔案路徑（`.claw/worker-state.json`），供外部 observer 輪詢

**建議路徑：** 選項 3 —— 在每次狀態變更時，把 `WorkerStatus` 發射到 `.claw/worker-state.json`。這完全落在 claw-code plugin 的能力範圍內，不需上游修改，也能讓 clawhip 透過輪詢檔案來區分真正卡住的 worker 與安靜但仍在前進的 worker。

**行動項目：** 將 `WorkerRegistry::transition()` 接上原子寫入 `.claw/worker-state.json`。新增 `claw state` CLI subcommand 來讀取並印出這個檔案。補上 regression test。

**先前 session 的錯誤說法：** 曾有一份 session summary 宣稱 commit `0984cca` 已透過 axum 落地 `/state` HTTP endpoint。這是不正確的：`main` 上不存在這個 commit，axum 也不是 dependency，而且 HTTP server 不是我們的。真實已存在的工作是：`worker_boot.rs` 中的 `WorkerStatus` enum + `WorkerRegistry`，並已完整接入 `runtime/src/lib.rs` 作為 public exports。

## Startup Friction Gap：Settings 中沒有預設 trusted_roots（記錄於 2026-04-08）

### 除非呼叫端顯式傳 roots，否則每條 lane 都會從人工 trust babysitting 開始

**這是在直接 dogfood WorkerCreate tool 時發現的 root cause。**

`WorkerCreate` 接受 `trusted_roots: Vec<String>` 參數。如果呼叫端省略它（或傳 `[]`），每個新 worker 都會立刻進入 `TrustRequired` 並停住，必須人工干預才會進到 `ReadyForPrompt`。現在沒有任何機制可以在 `settings.json` 或 `.claw/settings.json` 中設定預設 allowlist。

**影響：** batch tooling（clawhip、lane orchestrators）必須在每次 `WorkerCreate` 呼叫時都顯式傳入 `trusted_roots`。如果 batch script 忘了帶這個欄位，該批所有 workers 都會默默卡在 `trust_required`。這正是多次「batch 8 lanes 沒有前進」事故的 root cause。

**建議修復：**
1. 在 `RuntimeConfig` 中新增 `trusted_roots` 欄位（或巢狀 `[trust]` table），並透過 `ConfigLoader` 載入
2. 在 `WorkerRegistry::spawn_worker()` 中，把 config-level `trusted_roots` 與每次呼叫的 overrides 合併
3. 預設值維持空列表（最安全）；由使用者自行在 settings 中加入 repo paths 以 opt in
4. 更新 `config_validate` schema，納入新欄位

**行動項目：** 將 `RuntimeConfig::trusted_roots()` 接到 `WorkerRegistry::spawn_worker()` 的預設邏輯。補上測試：若 config 中有 `trusted_roots = ["/tmp"]`，則在 `/tmp/x` 啟動 worker 時，即使呼叫端沒傳這個欄位，也能 auto-resolve trust。

## Observability Transport Decision（記錄於 2026-04-08）

### Canonical state surface：CLI/file-based。HTTP endpoint 延後。

**決策：** `claw state` 讀取 `.claw/worker-state.json` 是 clawhip 與下游工具的**正式 observability contract**。這不是過渡方案，而是受支持的 surface。請直接以它為基礎建構。

**理由：**

- claw-code 是在 opencode binary 內運作的 plugin，無法替 `opencode serve` 增加 HTTP routes；那個 server 屬於上游 `sst/opencode`
- file-based surface 完全落在 plugin 能力範圍內：`worker_boot.rs` 的 `emit_state_file()` 會在每次 `WorkerStatus` transition 時做原子寫入
- `claw state --output-format json` 已提供 clawhip 所需的全部資訊：`status`、`is_ready`、`seconds_since_update`、`trust_gate_cleared`、`last_event`、`updated_at`
- 輪詢本地檔案的延遲更低，失敗模式也比打 sidecar HTTP round-trip 更少
- 若要有 HTTP state endpoint，不是要 upstream 一條 route 到 `sst/opencode`（可能要數週 PR cycle，且不保證會被接受），就是要做一個 sidecar process 去 in-process 查 `WorkerRegistry`，這兩者都更脆弱，還增加額外 failure domain

**下游工具（clawhip）應如何使用：**
1. 在 `WorkerCreate` 後，於 worker 的 CWD 輪詢 `.claw/worker-state.json`（或執行 `claw state --output-format json`），輪詢間隔可自行決定，例如 5 秒
2. 若 `trust_required` 狀態下的 `seconds_since_update > 60`，就視為 stall signal
3. 呼叫 `WorkerResolveTrust` tool 解除阻塞，或呼叫 `WorkerRestart` 重置

**HTTP endpoint tracking：** 目前未排程。若未來出現 file polling 無法滿足的具體 use case（例如遠端 workers 跨 network boundary），再另開 issue，把 `/worker/state` route upstream 到 `sst/opencode`。在那之前：file/CLI 就是 canonical。
