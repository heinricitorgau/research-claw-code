# Claw Code 哲學

## 不要只盯著這些檔案看

如果你只是在看這個儲存庫裡生成出來的檔案，那你看的其實是錯的層。

Python 重寫只是副產品。Rust 重寫也只是副產品。真正值得研究的是**產生這些成果的系統**：一個以 clawhip 為基礎的協作循環，由人類給方向，自治 claws 負責執行工作。

Claw Code 不只是一個 codebase。它更像是一個公開展示，說明當以下條件同時成立時會發生什麼：

- 人類提供清楚方向
- 多個 coding agents 並行協作
- notification routing 被移出 agent 的 context window
- planning、execution、review 與 retry loops 被自動化
- 而人類**不需要**坐在 terminal 前逐步 micromanage 每個動作

## 真正的人機介面是 Discord

這裡重要的介面不是 tmux、Vim、SSH，或 terminal multiplexer。

真正的人類介面是一個 Discord channel。

一個人可以用手機打一段話，然後離開、睡覺，或去做別的事。claws 會讀取指令、拆成任務、分配角色、寫程式、跑測試、針對失敗爭論、修復，最後在工作通過時 push。

這就是它的哲學：**人類設定方向；claws 負責勞動。**

## 三段式系統

### 1. OmX (`oh-my-codex`)
[oh-my-codex](https://github.com/Yeachan-Heo/oh-my-codex) 提供 workflow layer。

它把短指令轉成結構化執行：

- planning keywords
- execution modes
- persistent verification loops
- parallel multi-agent workflows

這一層負責把一句話轉成可重複執行的工作協定。

### 2. clawhip
[clawhip](https://github.com/Yeachan-Heo/clawhip) 是 event 與 notification router。

它監看：

- git commits
- tmux sessions
- GitHub issues 與 PRs
- agent lifecycle events
- channel delivery

它的工作是把監控與傳遞**留在 coding agent 的 context window 之外**，讓 agents 可以專注在 implementation，而不是 status formatting 與 notification routing。

### 3. OmO (`oh-my-openagent`)
[oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent) 處理 multi-agent coordination。

planning、handoffs、disagreement resolution，以及 verification loops 都在這裡跨 agent 發生。

當 Architect、Executor 與 Reviewer 彼此不同意時，OmO 提供這個循環可以收斂而不是崩潰的結構。

## 真正的瓶頸改變了

現在的瓶頸已經不是打字速度。

當 agent systems 可以在幾小時內重建一個 codebase，稀缺資源就變成：

- architectural clarity
- task decomposition
- judgment
- taste
- 對什麼值得建構的 conviction
- 知道哪些部分可以並行、哪些部分必須受限

一個快速的 agent 團隊不會消除思考的必要。它只會讓清楚思考變得更有價值。

## Claw Code 展示了什麼

Claw Code 展示了一個儲存庫可以是：

- **在公開環境中自治建構**
- 由 claws/lobsters 協調，而不只是人類 pair-programming
- 透過 chat interface 操作
- 透過結構化的 planning/execution/review loops 持續改進
- 被維護成一個協作層的 showcase，而不只是輸出檔案本身

程式碼是證據。
協調系統才是產品層面的啟示。

## 真正持久重要的是什麼

隨著 coding intelligence 越來越便宜、越來越普及，真正持久的差異化不再是單純的程式輸出量。

真正仍然重要的是：

- product taste
- direction
- system design
- human trust
- operational stability
- 對下一步該建什麼的 judgment

在那樣的世界裡，人類的工作不是比機器更會打字。
人類的工作是決定什麼值得存在。

## 短版結論

**Claw Code 是一個自治軟體開發的展示。**

人類提供方向。
Claws 負責協調、建構、測試、修復並 push。
儲存庫是產物。
哲學則是其背後的系統。

## 延伸說明

如果你想看這套哲學更完整的公開說明，請參考：

- https://x.com/realsigridjin/status/2039472968624185713
