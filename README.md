# Mini-Agent System

一個以實驗為核心的 repository，用來研究：**最小化 agent loop 是否能在受控條件下改善軟體開發流程。**

## 使用方式

這個 repo 目前提供一套「可離線直接跑」的本地 AI 啟動流程。

### 1. 第一次準備離線 bundle

在有網路的機器上執行：

```bash
cd ~/Desktop/research-claw-code
bash deploy_local.sh
```

這一步會：

- 建置 `claw` CLI
- 準備本地 `ollama` 執行檔
- 下載並打包模型快取
- 產生 `local_ai/runtime/` 離線執行環境

### 2. 之後離線直接啟動

```bash
cd ~/Desktop/research-claw-code
bash local_ai/run.sh
```

一次性問句也可以直接跑：

```bash
bash local_ai/run.sh --output-format text prompt "幫我解釋這個 repo"
```

### 3. 搬到另一台電腦

把整個 `research-claw-code` 資料夾連同 `local_ai/runtime/` 一起複製過去即可。

注意：

- 不需要另外安裝 `ollama`
- 在 macOS 上不需要另外安裝 Python，launcher 會使用系統自帶的 `/usr/bin/python3`
- 目前 bundle 是「同作業系統、同 CPU 架構」可攜，例如 `macOS arm64 -> macOS arm64`

更完整的部署說明請看 [local_ai/README.md](./local_ai/README.md)。

## 研究問題

> **在保持可控性、可觀測性與可評估性的前提下，最小代理循環究竟能走多遠？**

這不是一個完整產品，也不是一個自治 agent framework。它是一個持續進行中的實驗環境，用來驗證以下問題：

- 一個簡單的 `Task -> Generate -> Evaluate -> Refine` 循環，是否能穩定提升輸出品質
- evaluation 是否可以作為一級能力，而不是事後補上的檢查
- human-in-the-loop 的控制模式，是否能和高度自動化共存
- 當迭代次數增加時，系統是收斂、停滯，還是發散

## 實驗循環

```text
Task -> Generate -> Evaluate -> Refine -> Repeat
```

這個循環的重點不是「一次就做對」，而是每一輪都產生可被評估的輸出、可被記錄的偏差、可作為下一輪輸入的修正資訊。如果沒有 evaluation，這個系統就只是在重複生成。如果沒有 refinement，就無法驗證系統是否在學習任何東西。

## 實驗假設

| 假設 | 驗證方向 |
|------|---------|
| 最小 agent loop 可以提升迭代效率 | 比較加入循環前後的修正速度與輸出品質 |
| evaluation 能降低 silent failure | 追蹤 failure 被發現、分類與修正的比例 |
| human-in-the-loop 可以保留控制而不顯著拖慢流程 | 觀察人工介入點數量與迭代速度之間的關係 |
| 輕量模型比複雜 orchestration 更容易定位因果 | 在低複雜度結構下記錄觀察結果與失敗原因 |

## 設計選擇

| 設計決策 | Rationale |
|---------|-----------|
| 最小代理抽象 | 複雜 orchestration 會污染實驗變數；模組越多，越難判斷哪個機制真正造成效果 |
| Task-driven（而不是 session-driven）| 讓每個實驗單位可以獨立評估與重現 |
| Evaluation-first（而不是 generation-first）| 如果 failure modes 不透明，就很難做出可信的研究結論 |
| Feedback-based refinement（而不是單純重試 prompt）| 區分「生成失敗」與「評估失敗」，使改進方向更明確 |
| Observability 優先於功能堆疊 | 可觀察的 failure 比更多功能更能推進研究 |

## 研究範圍

這個 repository 目前聚焦於 agent loop 的收斂性、evaluation 設計對 refinement 方向的影響、prompt 結構對可評估性的影響、error handling 與 retry / re-plan 的邊界，以及多輪 feedback 下的行為穩定性。這些問題屬於「受控 AI-assisted development」的研究範圍，而不是通用自治系統開發。

## Repository 結構

```text
.
├── src/        # 核心實驗邏輯與循環實作
├── tests/      # 驗證、回歸與評估測試
├── docs/       # 實驗筆記、設計備忘與觀察結果
└── assets/     # 輔助材料
```

## 研究模式執行

```bash
python -m src.main
```

如果行為與輸出會改變，通常是因為實驗本身仍在演化，而不是單純的使用錯誤。

## 目前狀態

| 項目 | 狀態 |
|------|------|
| 核心循環 | 早期驗證中 |
| Evaluation 機制 | 持續調整中 |
| 任務格式 | 實驗性 |
| 可觀測性 | 基礎層已建立 |
| 可重現性 | 持續補強中 |

## 如何閱讀這個專案

| 文件 | 說明 |
|------|------|
| `README.md` | 正在驗證什麼、核心研究問題 |
| `PHILOSOPHY.md` | 實驗立場、設計選擇的 rationale、開放問題 |
| `ROADMAP.md` | 下一階段要驗證什麼、已知問題清單 |
| `PARITY.md` | 目前 checkpoint 狀態、哪些能力有可驗證證據 |

## 已知限制

這個 repository 不是 production-ready system，不宣稱 fully autonomous operation，不代表完整 agent architecture 的最終結論，也不應被解讀成對所有 AI-assisted development workflow 的普遍證明。它的價值在於提供一個可持續 refinement 的實驗場，而不是直接給出結論。

## 開放問題

- 目前的 evaluation 設計是否能區分「模型本身的限制」與「任務描述不夠清楚」這兩種失敗來源？
- human-in-the-loop 的介入點設計，是否有可能演化成更少、但更精準的形式？
- 當迭代輪數增加後，refinement 信號是否仍然有效，還是會出現噪音累積的問題？

---

作者：Heinnrici
