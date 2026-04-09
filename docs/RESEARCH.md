# Claw Code 研究報告

**最後更新：** 2026-04-09
**作者：** Heinnrici
**版本：** v1.0

---

## 摘要

本報告記錄 **Claw Code** 專案的核心研究成果與系統設計洞見。Claw Code 是一個以 Rust 重寫的 Claude Code，目的是探索「clawable」（機器優先）的 coding harness 設計，以及在 AI 輔助開發環境中，如何透過多代理協調系統讓人類以最少干預完成複雜的軟體開發工作。

核心命題：**當 coding intelligence 越來越便宜，真正的稀缺資源是方向、判斷與架構清晰度，而不是程式碼輸出量。**

---

## 1. 研究背景與動機

### 1.1 問題陳述

傳統 AI 輔助開發工具（包括原始 Claude Code）的設計前提是：主要使用者是坐在 terminal 前的人類開發者。這帶來了根本性的限制：

- session 啟動依賴人工操作（trust prompts、terminal 互動）
- 系統狀態散落在 tmux、git、tests 等多層之間，難以機器讀取
- 錯誤分類依賴文字解析（scraping prose），而非結構化 events
- 復原流程需要人工介入（restart worker、重新注入 prompt）
- 設計假設人類在場盯著 terminal，而非讓 claws 自主操作

### 1.2 研究目標

設計並實作一個「clawable」的 coding harness：

1. 可被機器**可決定性地啟動**
2. 狀態與 failure modes **可被機器讀取**
3. **不需要人類盯著 terminal** 也能恢復
4. 以 **event 為先**，而不是以 log scraping 為先
5. **policy 可執行**（merge、retry、rebase 由機器完成）

---

## 2. 系統架構

### 2.1 三層協調架構

Claw Code 建立在三個相互配合的子系統上：

```
Discord（人類介面）
        │
        ▼
   OmX（指令轉工作流）
        │
        ▼
  clawhip（事件路由）
        │
        ▼
   OmO（多代理協調）
        │
        ▼
  claw workers（執行層）
        │
        ▼
  git / tests / infra
```

#### Layer 1：OmX（oh-my-codex）— 工作流層

將短指令轉成結構化執行協定：

- **planning keywords**：解析人類指令，拆解成可執行任務
- **execution modes**：定義單代理 vs 多代理執行策略
- **persistent verification loops**：確保輸出通過驗收再交付
- **parallel multi-agent workflows**：多個 claw workers 並行協作

**關鍵洞見**：一句話指令可以透過 OmX 轉成可重複執行的工作協定，消除了每次都要重新描述細節的摩擦。

#### Layer 2：clawhip — 事件路由層

監看並路由來自各層的事件：

- git commits / PRs / Issues
- tmux sessions
- agent lifecycle events
- GitHub CI 狀態

**設計選擇**：clawhip 刻意把監控與傳遞**留在 coding agent 的 context window 之外**。agents 只專注在實作，不需要格式化 status updates 或路由 notifications。

#### Layer 3：OmO（oh-my-openagent）— 多代理協調層

處理多代理的協調問題：
- planning 與 handoffs
- disagreement resolution（Architect vs Executor vs Reviewer 意見分歧時的收斂機制）
- verification loops 的跨代理執行

### 2.2 人機介面：Discord

最重要的設計決策之一：**真正的人類介面是 Discord，不是 terminal**。

一個人可以用手機打一段話，然後離開、睡覺，或去做別的事。claws 會：
1. 讀取指令
2. 拆解成任務
3. 分配角色
4. 寫程式
5. 跑測試
6. 針對失敗爭論並修復
7. 測試通過後 push

**這代表什麼**：人類的工作從「micromanage 每個 terminal 動作」，轉變為「設定方向、做判斷」。

---

## 3. Rust Port：技術實作

### 3.1 整體規模

| 指標 | 數值 |
|------|------|
| main 上的 commits | 292 |
| Rust crates 數量 | 9 |
| 受追蹤 Rust LOC | 48,599 行 |
| 測試 LOC | 2,568 行 |
| 參與作者 | 3 位 |
| 開發時間跨度 | 2026-03-31 → 2026-04-03（約 3 天） |
| Mock parity scenarios | 10 個 |
| 捕捉的 API requests | 19 個 `/v1/messages` requests |

### 3.2 九條功能 Lanes

全部 9 條 lanes 已合併到 `main`：

| Lane | 功能 | 規模 | 核心模組 |
|------|------|------|---------|
| 1 | Bash validation | +1004 LOC | `bash_validation.rs` — readOnlyValidation、destructiveCommandWarning、modeValidation、sedValidation、pathValidation、commandSemantics |
| 2 | CI fix | +22/-1 | `sandbox.rs` — 用真實 capability probe 取代 binary 存在假設 |
| 3 | File-tool | 744 LOC | `file_ops.rs` — binary detection、size limits、workspace boundary、symlink escape |
| 4 | TaskRegistry | 335 LOC | `task_registry.rs` — thread-safe in-memory task lifecycle（create/get/list/stop/update/output） |
| 5 | Task wiring | 79/-35 | `tools/lib.rs` — TaskRegistry 接到 6 個 task tools |
| 6 | Team+Cron | 363 LOC | `team_cron_registry.rs` — TeamRegistry + CronRegistry |
| 7 | MCP lifecycle | 406 LOC | `mcp_tool_bridge.rs` — MCP lifecycle bridge（connection status、resource listing、tool dispatch） |
| 8 | LSP client | 438 LOC | `lsp_client.rs` — diagnostics、hover、definition、references、completion、symbols |
| 9 | Permission enforcement | 340 LOC | `permission_enforcer.rs` — tool gating、file write boundary、bash read-only heuristics |

### 3.3 Mock Parity Harness

為了驗證 Rust port 的行為與原版 Claude Code 一致，建立了 mock parity harness：

**設計原則**：
- 可決定性（deterministic）的 scripted scenarios
- 乾淨環境（clean-env）的 test runner
- 與 Anthropic API 相容的 mock service

**已驗證的 scenarios**：

| Scenario | 驗證內容 |
|----------|---------|
| `streaming_text` | streaming response handling |
| `read_file_roundtrip` | read path execution + synthesis |
| `grep_chunk_assembly` | chunked grep output handling |
| `write_file_allowed` | write success |
| `write_file_denied` | permission denial |
| `multi_tool_turn_roundtrip` | multi-tool assistant turns |
| `bash_stdout_roundtrip` | bash execution flow |
| `bash_permission_prompt_approved` | permission prompt handling（approved） |
| `bash_permission_prompt_denied` | permission prompt handling（denied） |
| `plugin_tool_roundtrip` | plugin tool execution path |

---

## 4. 「Clawable」設計原則

### 4.1 七個產品原則

1. **State machine first**：每個 worker 都有明確 lifecycle states（spawning → trust_required → ready_for_prompt → running → blocked → finished/failed）
2. **Events over scraped prose**：channel output 由 typed events 推導，不靠文字解析
3. **Recovery before escalation**：已知 failure modes 先自動修復，再決定是否求助
4. **Branch freshness before blame**：先檢查 stale branch，再把紅測試當成新 regression
5. **Partial success is first-class**：MCP startup 可以部分成功、部分失敗，需有 degraded-mode reporting
6. **Terminal is transport, not truth**：tmux/TUI 是實作細節，orchestration state 活在更高一層
7. **Policy is executable**：merge、retry、rebase、stale cleanup 由機器執行，不只是聊天指令

### 4.2 Failure Taxonomy（失敗分類體系）

明確分類所有可能的 failure，使自動化 retry policy 可依 failure type 分流：

```
prompt_delivery    → 重新送 prompt
trust_gate         → auto-trust 或 escalate
branch_divergence  → rebase/stale cleanup
compile            → 修編譯錯誤
test               → 修測試
plugin_startup     → 重試 plugin 初始化
mcp_startup        → 重試 MCP 連線
mcp_handshake      → 協議層修復
gateway_routing    → 路由修復
tool_runtime       → tool 執行層修復
infra              → 基礎設施 escalate
```

---

## 5. 研究發現與洞見

### 5.1 真正的瓶頸已改變

當 agent systems 可以在幾小時內重建一個 codebase，稀缺資源不再是打字速度。

**新的稀缺資源**：
- Architectural clarity（架構清晰度）
- Task decomposition（任務拆解能力）
- Judgment（判斷力）
- Taste（品味）
- 對什麼值得建構的 conviction
- 知道哪些部分可並行、哪些必須受限

**意涵**：快速的 agent 團隊不會消除思考的必要，它只會讓清楚思考變得更有價值。

### 5.2 機器可讀性是一等設計屬性

傳統 coding 工具設計給人類閱讀（log 文字、terminal output）。在 multi-agent 系統中，**機器可讀性（machine readability）需要與人類可讀性同等對待**，或更優先。

關鍵設計決策：
- Typed events 取代 log scraping
- Structured state machines 取代隱性狀態
- Explicit failure taxonomy 取代「看 log 猜原因」

### 5.3 人機介面的重新定義

最反直覺的洞見：**terminal 不應該是主要人機介面**。

當系統設計成讓人類透過 Discord 給方向，claws 自主完成工作，帶來了：
- 人類可以在任何地方、用任何設備工作
- 沒有「必須坐在電腦前」的認知負擔
- claws 的 context window 不被 UI 狀態管理佔用

### 5.4 Parity Testing 的重要性

在重寫（rewrite）專案中，**行為一致性比程式碼一致性更重要**。

Mock parity harness 的價值：
- 在沒有真實 API key 的情況下驗證行為
- 可決定性地重現特定 scenarios
- 防止行為 regression 進入 main

### 5.5 並行 Lane 開發的效率

9 個 feature lanes 在約 3 天內完成（2026-03-31 → 2026-04-03），達到 48,599 行 Rust LOC。

這代表：
- 每天約 16,000 行受追蹤 Rust code
- 並行開發（多個 lanes 同時進行）是關鍵
- Typed interfaces between layers 讓並行成為可能（lanes 互相不阻塞）

---

## 6. 當前限制與未解問題

### 6.1 已知技術限制

| 限制 | 說明 |
|------|------|
| Bash validation lanes 仍不完整 | Upstream 有 18 個 submodules，Rust 目前只有 1 個 |
| Team/Cron 尚未接到真實 scheduler | 目前只有 in-memory registry，未連接真實 background scheduler |
| MCP end-to-end 連線 | registry bridge 已到位，但完整 transport/runtime 深度仍待完成 |
| LSP completion/format | registry model 存在，但 external language-server process orchestration 仍是獨立工作 |

### 6.2 架構未解問題

**Session 啟動穩定性**：
- trust prompts 可能阻塞 TUI 啟動
- 「session exists」≠「session is ready」
- shell 誤投遞（prompt 落進 shell 而非 coding agent）仍可能發生

**事件系統完整性**：
- claws 目前仍必須從 noisy text 中推斷部分狀態
- 關鍵狀態尚未全部正規化為 machine-readable events

**Recovery loop 的自動化程度**：
- 部分 recovery 仍需人工介入
- 特別是 infra-level failures 的自動分類仍不足

---

## 7. 路線圖摘要

### Phase 1 — Reliable Worker Boot
- Coding workers 的 ready-handshake lifecycle（明確狀態機）
- Trust prompt resolver（auto-trust for known repos）
- Structured session control API（取代 raw send-keys）

### Phase 2 — Event-Native Clawhip Integration
- Canonical lane event schema（typed events）
- Failure taxonomy 實作（11 種 failure classes）
- Actionable summary compression（phase / checkpoint / blocker / recovery action）

### Phase 3 — Branch/Test Awareness and Auto-Recovery
- Stale-branch detection（大範圍驗證前先做）
- Automated recovery for known failure modes

---

## 8. 結論

Claw Code 展示了一個重要的設計轉移：

**從「人類使用 AI 工具」到「AI 代理使用人類方向」。**

在這個模型中：
- 程式碼是產物，不是工作
- 系統可觀測性（observability）是設計屬性，不是事後追加
- 人類的核心貢獻是 **conviction**（相信什麼值得建構）、**direction**（往哪裡走）、**judgment**（哪些決策不該自動化）

這套哲學不只適用於 claw-code 自身，也適用於任何需要在 AI-native 環境中維持人類掌控力的系統設計。

---

## 附錄

### A. 關鍵檔案索引

| 檔案 | 說明 |
|------|------|
| `PHILOSOPHY.md` | 系統哲學與設計背景 |
| `ROADMAP.md` | 詳細路線圖（Phase 1-3） |
| `PARITY.md` | 9-lane checkpoint 狀態與 mock parity harness |
| `USAGE.md` | Rust workspace 使用說明 |
| `docs/container.md` | Container-first 工作流（Docker/Podman） |
| `rust/crates/runtime/` | 核心 runtime（sandbox、file_ops、task_registry、lsp_client 等） |
| `rust/crates/tools/` | Tool dispatch layer |
| `rust/crates/rusty-claude-cli/` | CLI binary 與 mock parity harness |

### B. 相關外部資源

- [oh-my-codex (OmX)](https://github.com/Yeachan-Heo/oh-my-codex) — workflow layer
- [clawhip](https://github.com/Yeachan-Heo/clawhip) — event/notification router
- [oh-my-openagent (OmO)](https://github.com/code-yeongyu/oh-my-openagent) — multi-agent coordination
- [設計哲學延伸說明](https://x.com/realsigridjin/status/2039472968624185713)

---

*本文件基於 claw-code repository 截至 2026-04-09 的狀態。*
