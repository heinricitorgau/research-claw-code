# TEST_RECORD — Experimental Hardening Session

**Date:** 2026-04-12  
**Branch:** `test/experimental-hardening`  
**Test runner:** Python `unittest` (stdlib — no external deps needed)  
**Total tests after session:** 86 (22 pre-existing + 64 new) — all green ✅

---

## Hypothesis Table

| # | Hypothesis | Test Scenario | Expected | Actual | Status |
|---|-----------|---------------|----------|--------|--------|
| H1-a | `deny_names` block is case-insensitive | `blocks("BASHTOOL")` with `deny_names=["BashTool"]` | True | True | ✅ PASS |
| H1-b | `deny_names` block is case-insensitive (lower) | `blocks("bashtool")` with `deny_names=["BashTool"]` | True | True | ✅ PASS |
| H1-c | `deny_prefixes` block is case-insensitive | `blocks("MCPTool")` with `deny_prefixes=["mcp"]` | True | True | ✅ PASS |
| H1-d | Empty context blocks nothing | `blocks("BashTool")` on empty context | False | False | ✅ PASS |
| H1-e | Multiple deny_names | `blocks("BASHTOOL")` and `blocks("fileedittool")` | True × 2 | True × 2 | ✅ PASS |
| H2-a | **BUG** Empty deny_prefix silently blocks all tools | `blocks("BashTool")` with `deny_prefixes=[""]` | False (after fix) | False ✅ | **FIXED** |
| H2-b | `None` deny_prefixes is safe | `from_iterables(deny_prefixes=None)` | No error, blocks nothing | Correct | ✅ PASS |
| H2-c | Whitespace-only prefix is not meaningful | `deny_prefixes=["   "]` does not block `"BashTool"` | False | False | ✅ PASS |
| H3-a | Empty strings add 0 tokens | `add_turn("", "")` on base `(10, 5)` | `(10, 5)` | `(10, 5)` | ✅ PASS |
| H3-b | Single word adds 1 token each | `add_turn("hello", "world")` | `(1, 1)` | `(1, 1)` | ✅ PASS |
| H3-c | Multi-word counted by split | `add_turn("one two three four five", "alpha beta")` | `(5, 2)` | `(5, 2)` | ✅ PASS |
| H3-d | Cumulative turns accumulate | 2 turns: `"a b"` + `"d e f"` / `"c"` + `"g h"` | `(5, 3)` | `(5, 3)` | ✅ PASS |
| H3-e | `UsageSummary` is immutable | Original unchanged after `add_turn` | `(100, 50)` | `(100, 50)` | ✅ PASS |
| H4-a | `compact(3)` retains last 3 entries | 5-entry store, compact(3) | `["c","d","e"]` | `["c","d","e"]` | ✅ PASS |
| H4-b | `compact(N)` where N = len: no-op | compact(3) on 3-entry store | 3 entries | 3 entries | ✅ PASS |
| H4-c | `compact(N)` where N > len: no-op | compact(10) on 2-entry store | 2 entries | 2 entries | ✅ PASS |
| H4-d | **BUG** `compact(0)` must clear store | Python `-0 == 0` makes `entries[-0:]` keep all | 0 entries (after fix) | 0 entries ✅ | **FIXED** |
| H4-e | `flush()` sets `flushed=True` | Call `flush()` | `flushed == True` | True | ✅ PASS |
| H4-f | `append()` resets `flushed` flag | flush then append | `flushed == False` | False | ✅ PASS |
| H4-g | `replay()` returns a tuple snapshot | Call `replay()` | `tuple` type | `tuple` | ✅ PASS |
| H5-a | Normal submit_message completes | 1 message under limit | `stop_reason="completed"` | "completed" | ✅ PASS |
| H5-b | 9th message on `max_turns=8` is blocked | Fill 8, attempt 9th | `stop_reason="max_turns_reached"` | "max_turns_reached" | ✅ PASS |
| H5-c | `max_turns=0` blocks first message | Attempt first message | `stop_reason="max_turns_reached"` | "max_turns_reached" | ✅ PASS |
| H5-d | Blocked message not appended | Message count unchanged after rejection | `len` stable | Stable | ✅ PASS |
| H5-e | Matched commands & tools reflected | Pass `matched_commands=("review",)` | `result.matched_commands` contains "review" | Correct | ✅ PASS |
| H6-a | `structured_output=True` emits valid JSON | Call `submit_message("test")` | Parseable JSON | Parseable | ✅ PASS |
| H6-b | Structured JSON contains prompt text | Submit "find security issues" | Summary contains the prompt | Correct | ✅ PASS |
| H7-a | Stream first event is `message_start` | `stream_submit_message("hello")` | First type = "message_start" | Correct | ✅ PASS |
| H7-b | Stream last event is `message_stop` | Same | Last type = "message_stop" | Correct | ✅ PASS |
| H7-c | `message_stop` has `stop_reason` and `usage` | Same | Both keys present | Correct | ✅ PASS |
| H7-d | `command_match` event emitted with commands | Pass `matched_commands=("review",)` | Event type present | Correct | ✅ PASS |
| H7-e | `tool_match` event emitted with tools | Pass `matched_tools=("BashTool",)` | Event type present | Correct | ✅ PASS |
| H7-f | No `command_match` when none provided | No matched_commands | Event type absent | Absent | ✅ PASS |
| H7-g | `permission_denial` event emitted | Pass `denied_tools=(denial,)` | Event type present | Correct | ✅ PASS |
| H8-a | `get_command` is case-insensitive | `get_command(name.upper())` | Not None | Not None | ✅ PASS |
| H8-b | `get_command` unknown → None | `get_command("zzz_xyz")` | None | None | ✅ PASS |
| H8-c | `get_command("")` → None (adversarial) | `get_command("")` | None | None | ✅ PASS |
| H8-d | `execute_command` known → `handled=True` | Known command name | `handled=True`, message mentions name | Correct | ✅ PASS |
| H8-e | `execute_command` unknown → `handled=False` | Unknown command | `handled=False`, "Unknown mirrored command" | Correct | ✅ PASS |
| H8-f | `find_commands("")` returns all (edge) | Empty query | All commands returned | All matched | ✅ PASS |
| H8-g | `find_commands("zzz_no_match")` → empty | No-match query | `[]` | `[]` | ✅ PASS |
| H8-h | `get_commands(include_plugin_commands=False)` filters | Plugin filter | Subset ≤ full | Correct | ✅ PASS |
| H9-a | `None` context returns all tools | `filter_tools_by_permission_context(tools, None)` | Full list | Full list | ✅ PASS |
| H9-b | Deny name removes exactly that tool | Deny first tool by name | That tool absent | Absent | ✅ PASS |
| H9-c | Deny prefix `"mcp"` removes all MCP tools | `deny_prefixes=["mcp"]` | No `mcp*` tools remain | Correct | ✅ PASS |
| H9-d | Empty deny_names → no tools removed | `deny_names=[]` | Full list | Full list | ✅ PASS |
| H10-a | Empty temp dir → 0 Python files | `build_port_manifest(Path(tmp_empty))` | `total_python_files=0` | 0 | ✅ PASS |
| H10-b | One `.py` → count 1 | 1 `.py` file in temp | `total_python_files=1` | 1 | ✅ PASS |
| H10-c | Non-`.py` files ignored | `.py` + `.txt` + `.json` | `total_python_files=1` | 1 | ✅ PASS |
| H10-d | Nested `.py` files counted | 3 `.py` files in tree | `total_python_files=3` | 3 | ✅ PASS |
| H10-e | `to_markdown()` mentions root and count | Call `to_markdown()` | Contains "Port root:" and "Total Python files:" | Correct | ✅ PASS |
| H11-a | `ExecutionRegistry.command()` case-insensitive | Lookup by `.upper()` and `.lower()` | Not None | Correct | ✅ PASS |
| H11-b | `ExecutionRegistry.tool()` case-insensitive | Same | Not None | Correct | ✅ PASS |
| H11-c | Missing command → None | `command("ghost_xyz")` | None | None | ✅ PASS |
| H11-d | Missing tool → None | `tool("ghost_xyz")` | None | None | ✅ PASS |
| H11-e | Found command execute → mirrored message | `cmd.execute("input")` | "Mirrored command" in result | Correct | ✅ PASS |
| H11-f | Found tool execute → mirrored message | `tool.execute("payload")` | "Mirrored tool" in result | Correct | ✅ PASS |
| H12-a | Empty `PortingBacklog.summary_lines()` | `PortingBacklog(title="empty")` | `[]` | `[]` | ✅ PASS |
| H12-b | Line count == module count | `build_command_backlog()` | Lengths equal | Equal | ✅ PASS |
| H12-c | Each line contains module name | First 5 modules | Name in line | Correct | ✅ PASS |
| H12-d | Each line contains `[mirrored]` status | First 5 lines | `[mirrored]` in line | Correct | ✅ PASS |

---

## Discovered Issues

### Bug 1 — `ToolPermissionContext`: Empty `deny_prefix` silently blocks all tools

**File:** `src/permissions.py`  
**Severity:** High  
**Category:** Adversarial input / security misconfiguration  

**Description:**  
`ToolPermissionContext.from_iterables(deny_prefixes=[""])` produced a context that blocked every single tool. Because `str.startswith("")` always returns `True` in Python, any empty string passed as a deny prefix would match every tool name. A caller passing `deny_prefixes=[""]` (e.g., via empty config entry or misconfiguration) would silently deny all tool use with no error or warning.

**Root cause:**  
No validation of prefix values in `from_iterables`. Empty strings were lowercased and stored as-is.

**Fix applied:**  
Filter out empty and whitespace-only strings from `deny_prefixes` during construction:
```python
deny_prefixes=tuple(
    p for p in (prefix.lower() for prefix in (deny_prefixes or []))
    if p.strip()
),
```

---

### Bug 2 — `TranscriptStore.compact(0)`: Python `-0 == 0` trap retains all entries

**File:** `src/transcript.py`  
**Severity:** Medium  
**Category:** Edge-case logic / off-by-one  

**Description:**  
Calling `compact(keep_last=0)` should reduce the transcript to zero entries (full clear). Instead, it kept all entries because `entries[-0:]` is evaluated as `entries[0:]` in Python (since `-0 == 0`), which is a full slice. The guard `if len(self.entries) > keep_last` evaluated as `5 > 0 = True`, entered the branch, but then `entries[-0:]` silently preserved everything.

The same pattern exists implicitly in `QueryEnginePort.compact_messages_if_needed` which calls `compact(self.config.compact_after_turns)`.

**Root cause:**  
Python does not distinguish `-0` from `0` for integers. The slice `seq[-0:]` is identical to `seq[0:]`.

**Fix applied:**  
Explicit guard for `keep_last == 0`:
```python
if keep_last == 0:
    self.entries.clear()
else:
    self.entries[:] = self.entries[-keep_last:]
```

---

## Fix Summary

| File | Change | Lines affected |
|------|--------|----------------|
| `src/permissions.py` | Filter empty/whitespace deny_prefixes in `from_iterables` | +4 (comment + filter expr) |
| `src/transcript.py` | Guard `compact(0)` with explicit `clear()` branch | +4 (comment + branch) |
| `tests/test_experimental_hardening.py` | 64 new hypothesis-driven tests across 12 test classes | +new file |

---

## Test Run Results

```
Ran 86 tests in 2.074s
OK
```

All 86 tests pass (22 pre-existing + 64 new experimental).

### New test file structure

| Test Class | Tests | Coverage Area |
|-----------|-------|---------------|
| `TestToolPermissionContextCaseInsensitivity` | 7 | Case-insensitive deny blocking |
| `TestToolPermissionContextAdversarialEmptyPrefix` | 3 | **Bug 1** adversarial prefix inputs |
| `TestUsageSummaryTokenCounting` | 5 | Token accumulation semantics |
| `TestTranscriptStoreCompact` | 7 | **Bug 2** compact(0) + flush/append |
| `TestQueryEngineMaxTurns` | 5 | Max-turns enforcement boundaries |
| `TestQueryEngineStructuredOutput` | 2 | JSON output validity |
| `TestQueryEngineStreamEvents` | 7 | SSE event ordering and types |
| `TestCommandsModuleRobustness` | 9 | Case-insensitive lookup, adversarial inputs |
| `TestToolsPermissionFiltering` | 4 | Tool permission gating |
| `TestPortManifestCustomRoot` | 5 | File counting with custom paths |
| `TestExecutionRegistryLookup` | 6 | Registry case-insensitive lookup |
| `TestPortingBacklogSummaryLines` | 4 | Summary line format correctness |

---

## Rust Codebase Notes (cargo not available in sandbox)

The `rust/` workspace contains extensive inline unit tests and integration tests across:

- `rust/crates/runtime/src/permissions.rs` — 11 `#[test]` functions covering `PermissionPolicy`, hook overrides, rule-based allow/deny/ask
- `rust/crates/runtime/src/bash_validation.rs` — 32 `#[test]` functions covering read-only validation, destructive command warnings, sed/path validation
- `rust/crates/runtime/tests/integration_tests.rs` — cross-module wiring tests (stale branch → policy engine, green contracts)
- `rust/crates/rusty-claude-cli/tests/` — CLI flag defaults, compact output, mock parity harness, output format contracts, resume/slash commands

These tests are verified by the CI (`rust-ci.yml`) and are expected to pass against the `rust/` workspace on a machine with a stable Rust toolchain.
