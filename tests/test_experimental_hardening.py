"""Experimental hardening test suite.

Each test class documents a Hypothesis, tests happy-path, edge-case, and
adversarial scenarios, and is self-contained so failures are easy to triage.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.models import PermissionDenial, UsageSummary
from src.permissions import ToolPermissionContext
from src.transcript import TranscriptStore


# ---------------------------------------------------------------------------
# H1 — ToolPermissionContext: case-insensitive deny_names
# Hypothesis: blocking is always case-insensitive regardless of input casing.
# ---------------------------------------------------------------------------
class TestToolPermissionContextCaseInsensitivity(unittest.TestCase):
    """H1: deny_names and deny_prefixes block regardless of input casing."""

    def test_blocks_exact_lowercase_name(self) -> None:
        ctx = ToolPermissionContext.from_iterables(deny_names=["BashTool"])
        self.assertTrue(ctx.blocks("bashtool"))

    def test_blocks_exact_uppercase_name(self) -> None:
        ctx = ToolPermissionContext.from_iterables(deny_names=["BashTool"])
        self.assertTrue(ctx.blocks("BASHTOOL"))

    def test_blocks_mixed_case_name(self) -> None:
        ctx = ToolPermissionContext.from_iterables(deny_names=["BashTool"])
        self.assertTrue(ctx.blocks("BashTool"))

    def test_does_not_block_unrelated_tool(self) -> None:
        ctx = ToolPermissionContext.from_iterables(deny_names=["BashTool"])
        self.assertFalse(ctx.blocks("FileReadTool"))

    def test_prefix_block_is_case_insensitive(self) -> None:
        ctx = ToolPermissionContext.from_iterables(deny_prefixes=["mcp"])
        self.assertTrue(ctx.blocks("MCPTool"))
        self.assertTrue(ctx.blocks("mcp_server"))
        self.assertFalse(ctx.blocks("BashTool"))

    def test_empty_context_blocks_nothing(self) -> None:
        ctx = ToolPermissionContext.from_iterables()
        self.assertFalse(ctx.blocks("BashTool"))
        self.assertFalse(ctx.blocks(""))

    def test_multiple_deny_names(self) -> None:
        ctx = ToolPermissionContext.from_iterables(deny_names=["BashTool", "FileEditTool"])
        self.assertTrue(ctx.blocks("BashTool"))
        self.assertTrue(ctx.blocks("fileedittool"))
        self.assertFalse(ctx.blocks("FileReadTool"))


# ---------------------------------------------------------------------------
# H2 — ToolPermissionContext: adversarial empty prefix
# Hypothesis: an empty string in deny_prefixes would accidentally block ALL
# tools because every string starts with "". This is a latent bug that must
# be guarded against.
# ---------------------------------------------------------------------------
class TestToolPermissionContextAdversarialEmptyPrefix(unittest.TestCase):
    """H2: Empty deny_prefix is an adversarial input — must be filtered out."""

    def test_empty_prefix_should_not_block_all_tools(self) -> None:
        """ADVERSARIAL: '' prefix would block everything — must be filtered."""
        ctx = ToolPermissionContext.from_iterables(deny_prefixes=[""])
        # After the fix: empty prefix is filtered, so no tools are blocked.
        self.assertFalse(ctx.blocks("BashTool"), "Empty prefix must not block all tools")
        self.assertFalse(ctx.blocks("FileReadTool"), "Empty prefix must not block all tools")

    def test_none_deny_prefixes_is_safe(self) -> None:
        ctx = ToolPermissionContext.from_iterables(deny_prefixes=None)
        self.assertFalse(ctx.blocks("BashTool"))

    def test_whitespace_only_prefix_is_not_a_meaningful_block(self) -> None:
        """Whitespace-only prefixes should be filtered to prevent unintended blocks."""
        ctx = ToolPermissionContext.from_iterables(deny_prefixes=["   "])
        # Whitespace prefix after strip should not block normal tool names
        self.assertFalse(ctx.blocks("BashTool"))


# ---------------------------------------------------------------------------
# H3 — UsageSummary: token counting semantics
# Hypothesis: add_turn counts whitespace-split words; empty strings = 0 tokens.
# ---------------------------------------------------------------------------
class TestUsageSummaryTokenCounting(unittest.TestCase):
    """H3: add_turn accumulates word-split token counts correctly."""

    def test_empty_prompt_and_output_add_zero(self) -> None:
        base = UsageSummary(input_tokens=10, output_tokens=5)
        result = base.add_turn("", "")
        self.assertEqual(result.input_tokens, 10)
        self.assertEqual(result.output_tokens, 5)

    def test_single_word_adds_one_token_each(self) -> None:
        base = UsageSummary()
        result = base.add_turn("hello", "world")
        self.assertEqual(result.input_tokens, 1)
        self.assertEqual(result.output_tokens, 1)

    def test_multi_word_prompt_counted_correctly(self) -> None:
        base = UsageSummary()
        result = base.add_turn("one two three four five", "alpha beta")
        self.assertEqual(result.input_tokens, 5)
        self.assertEqual(result.output_tokens, 2)

    def test_cumulative_turns_accumulate(self) -> None:
        usage = UsageSummary()
        usage = usage.add_turn("a b", "c")
        usage = usage.add_turn("d e f", "g h")
        self.assertEqual(usage.input_tokens, 5)  # 2 + 3
        self.assertEqual(usage.output_tokens, 3)  # 1 + 2

    def test_original_instance_is_immutable(self) -> None:
        base = UsageSummary(input_tokens=100, output_tokens=50)
        _ = base.add_turn("one two", "three")
        self.assertEqual(base.input_tokens, 100)
        self.assertEqual(base.output_tokens, 50)


# ---------------------------------------------------------------------------
# H4 — TranscriptStore: compact boundary conditions
# Hypothesis: compact(keep_last) retains exactly keep_last entries.
# Edge case: compact(0) should produce an empty store, not retain everything.
# ---------------------------------------------------------------------------
class TestTranscriptStoreCompact(unittest.TestCase):
    """H4: compact() respects keep_last boundary including zero."""

    def test_compact_reduces_to_keep_last(self) -> None:
        ts = TranscriptStore(entries=["a", "b", "c", "d", "e"])
        ts.compact(3)
        self.assertEqual(len(ts.entries), 3)
        self.assertEqual(ts.entries, ["c", "d", "e"])

    def test_compact_with_keep_last_equal_to_length(self) -> None:
        ts = TranscriptStore(entries=["a", "b", "c"])
        ts.compact(3)
        self.assertEqual(len(ts.entries), 3)

    def test_compact_with_keep_last_greater_than_length(self) -> None:
        ts = TranscriptStore(entries=["a", "b"])
        ts.compact(10)
        self.assertEqual(len(ts.entries), 2)

    def test_compact_zero_should_produce_empty_store(self) -> None:
        """EDGE CASE: compact(0) must clear all entries (Python -0 == 0 trap)."""
        ts = TranscriptStore(entries=["a", "b", "c", "d", "e"])
        ts.compact(0)
        self.assertEqual(len(ts.entries), 0, "compact(0) must empty the store")

    def test_flush_marks_flushed(self) -> None:
        ts = TranscriptStore(entries=["x"])
        self.assertFalse(ts.flushed)
        ts.flush()
        self.assertTrue(ts.flushed)

    def test_append_resets_flushed_flag(self) -> None:
        ts = TranscriptStore()
        ts.flush()
        self.assertTrue(ts.flushed)
        ts.append("new entry")
        self.assertFalse(ts.flushed)

    def test_replay_returns_tuple_snapshot(self) -> None:
        ts = TranscriptStore(entries=["a", "b", "c"])
        result = ts.replay()
        self.assertIsInstance(result, tuple)
        self.assertEqual(result, ("a", "b", "c"))


# ---------------------------------------------------------------------------
# H5 — QueryEnginePort: max_turns enforcement
# Hypothesis: when mutable_messages >= max_turns, submit_message returns
# stop_reason='max_turns_reached' without appending the new message.
# ---------------------------------------------------------------------------
class TestQueryEngineMaxTurns(unittest.TestCase):
    """H5: max_turns boundary is enforced correctly including zero."""

    def setUp(self) -> None:
        from src.query_engine import QueryEngineConfig, QueryEnginePort
        self.QueryEnginePort = QueryEnginePort
        self.QueryEngineConfig = QueryEngineConfig

    def _make_engine(self, max_turns: int) -> object:
        from src.port_manifest import build_port_manifest
        cfg = self.QueryEngineConfig(max_turns=max_turns)
        return self.QueryEnginePort(manifest=build_port_manifest(), config=cfg)

    def test_submit_message_under_limit_succeeds(self) -> None:
        engine = self._make_engine(max_turns=3)
        result = engine.submit_message("hello")
        self.assertEqual(result.stop_reason, "completed")
        self.assertIn("Prompt: hello", result.output)

    def test_submit_exactly_at_limit_returns_max_turns_reached(self) -> None:
        engine = self._make_engine(max_turns=2)
        engine.submit_message("turn 1")
        engine.submit_message("turn 2")
        result = engine.submit_message("turn 3 — should be blocked")
        self.assertEqual(result.stop_reason, "max_turns_reached")
        self.assertIn("Max turns reached", result.output)

    def test_max_turns_zero_blocks_first_message(self) -> None:
        """EDGE CASE: max_turns=0 → every message hits the limit immediately."""
        engine = self._make_engine(max_turns=0)
        result = engine.submit_message("immediate block")
        self.assertEqual(result.stop_reason, "max_turns_reached")

    def test_message_not_appended_when_max_turns_reached(self) -> None:
        engine = self._make_engine(max_turns=1)
        engine.submit_message("stored message")
        pre_count = len(engine.mutable_messages)
        engine.submit_message("rejected message")
        self.assertEqual(len(engine.mutable_messages), pre_count)

    def test_matched_commands_and_tools_reflected_in_result(self) -> None:
        engine = self._make_engine(max_turns=5)
        result = engine.submit_message(
            "analyze code",
            matched_commands=("review",),
            matched_tools=("BashTool",),
        )
        self.assertIn("review", result.matched_commands)
        self.assertIn("BashTool", result.matched_tools)


# ---------------------------------------------------------------------------
# H6 — QueryEnginePort: structured output produces valid JSON
# Hypothesis: structured_output=True always emits parseable JSON.
# ---------------------------------------------------------------------------
class TestQueryEngineStructuredOutput(unittest.TestCase):
    """H6: structured_output flag produces valid, parseable JSON."""

    def test_structured_output_is_valid_json(self) -> None:
        from src.port_manifest import build_port_manifest
        from src.query_engine import QueryEngineConfig, QueryEnginePort

        cfg = QueryEngineConfig(structured_output=True)
        engine = QueryEnginePort(manifest=build_port_manifest(), config=cfg)
        result = engine.submit_message("test prompt")
        parsed = json.loads(result.output)
        self.assertIn("summary", parsed)
        self.assertIn("session_id", parsed)

    def test_structured_output_contains_prompt(self) -> None:
        from src.port_manifest import build_port_manifest
        from src.query_engine import QueryEngineConfig, QueryEnginePort

        cfg = QueryEngineConfig(structured_output=True)
        engine = QueryEnginePort(manifest=build_port_manifest(), config=cfg)
        result = engine.submit_message("find security issues")
        parsed = json.loads(result.output)
        summary_text = " ".join(parsed["summary"])
        self.assertIn("find security issues", summary_text)


# ---------------------------------------------------------------------------
# H7 — QueryEnginePort stream events: ordering and types
# Hypothesis: stream_submit_message yields message_start first,
# message_stop last, and message_delta in between.
# ---------------------------------------------------------------------------
class TestQueryEngineStreamEvents(unittest.TestCase):
    """H7: streaming events have correct type sequence and fields."""

    def _collect_events(self, prompt: str, **kwargs) -> list[dict]:
        from src.port_manifest import build_port_manifest
        from src.query_engine import QueryEnginePort

        engine = QueryEnginePort(manifest=build_port_manifest())
        return list(engine.stream_submit_message(prompt, **kwargs))

    def test_first_event_is_message_start(self) -> None:
        events = self._collect_events("hello")
        self.assertEqual(events[0]["type"], "message_start")

    def test_last_event_is_message_stop(self) -> None:
        events = self._collect_events("hello")
        self.assertEqual(events[-1]["type"], "message_stop")

    def test_message_stop_has_stop_reason_and_usage(self) -> None:
        events = self._collect_events("hello")
        stop = events[-1]
        self.assertIn("stop_reason", stop)
        self.assertIn("usage", stop)
        self.assertIn("input_tokens", stop["usage"])

    def test_command_match_event_emitted_when_commands_present(self) -> None:
        events = self._collect_events("review code", matched_commands=("review",))
        types = [e["type"] for e in events]
        self.assertIn("command_match", types)

    def test_tool_match_event_emitted_when_tools_present(self) -> None:
        events = self._collect_events("run bash", matched_tools=("BashTool",))
        types = [e["type"] for e in events]
        self.assertIn("tool_match", types)

    def test_no_command_match_event_when_none_provided(self) -> None:
        events = self._collect_events("just a prompt")
        types = [e["type"] for e in events]
        self.assertNotIn("command_match", types)

    def test_permission_denial_event_emitted(self) -> None:
        denial = PermissionDenial(tool_name="DangerTool", reason="blocked")
        events = self._collect_events("attempt", denied_tools=(denial,))
        types = [e["type"] for e in events]
        self.assertIn("permission_denial", types)


# ---------------------------------------------------------------------------
# H8 — commands module: get_command and execute_command robustness
# Hypothesis: case-insensitive lookup works; unknown names return None/False.
# ---------------------------------------------------------------------------
class TestCommandsModuleRobustness(unittest.TestCase):
    """H8: command lookup is case-insensitive; unknowns handled gracefully."""

    def setUp(self) -> None:
        from src.commands import PORTED_COMMANDS
        self._any_valid_name = PORTED_COMMANDS[0].name

    def test_get_command_lowercase(self) -> None:
        from src.commands import get_command
        result = get_command(self._any_valid_name.lower())
        self.assertIsNotNone(result)
        self.assertEqual(result.name, self._any_valid_name)

    def test_get_command_uppercase(self) -> None:
        from src.commands import get_command
        result = get_command(self._any_valid_name.upper())
        self.assertIsNotNone(result)

    def test_get_command_unknown_returns_none(self) -> None:
        from src.commands import get_command
        self.assertIsNone(get_command("totally_nonexistent_command_xyz_abc"))

    def test_get_command_empty_string_returns_none(self) -> None:
        """ADVERSARIAL: empty string lookup must not raise or return garbage."""
        from src.commands import get_command
        self.assertIsNone(get_command(""))

    def test_execute_command_known_returns_handled_true(self) -> None:
        from src.commands import execute_command
        result = execute_command(self._any_valid_name, "some prompt")
        self.assertTrue(result.handled)
        self.assertIn(self._any_valid_name, result.message)

    def test_execute_command_unknown_returns_handled_false(self) -> None:
        from src.commands import execute_command
        result = execute_command("ghost_command_xyz", "prompt")
        self.assertFalse(result.handled)
        self.assertIn("Unknown mirrored command", result.message)

    def test_find_commands_empty_query_matches_all(self) -> None:
        """EDGE CASE: empty query string matches every command (starts-with '')."""
        from src.commands import PORTED_COMMANDS, find_commands
        results = find_commands("", limit=9999)
        self.assertEqual(len(results), len(PORTED_COMMANDS))

    def test_find_commands_nonexistent_query_returns_empty(self) -> None:
        from src.commands import find_commands
        results = find_commands("zzz_no_match_xyzzy_9999")
        self.assertEqual(results, [])

    def test_get_commands_excludes_plugin_commands(self) -> None:
        from src.commands import get_commands
        all_cmds = get_commands(include_plugin_commands=True)
        no_plugin = get_commands(include_plugin_commands=False)
        self.assertLessEqual(len(no_plugin), len(all_cmds))


# ---------------------------------------------------------------------------
# H9 — tools module: filter_tools_by_permission_context
# Hypothesis: permission context correctly gates tool access.
# ---------------------------------------------------------------------------
class TestToolsPermissionFiltering(unittest.TestCase):
    """H9: filter_tools_by_permission_context removes blocked tools."""

    def test_none_context_returns_all_tools(self) -> None:
        from src.tools import PORTED_TOOLS, filter_tools_by_permission_context
        result = filter_tools_by_permission_context(PORTED_TOOLS, None)
        self.assertEqual(len(result), len(PORTED_TOOLS))

    def test_context_with_deny_name_removes_that_tool(self) -> None:
        from src.tools import PORTED_TOOLS, filter_tools_by_permission_context
        first_tool_name = PORTED_TOOLS[0].name
        ctx = ToolPermissionContext.from_iterables(deny_names=[first_tool_name])
        result = filter_tools_by_permission_context(PORTED_TOOLS, ctx)
        names = [t.name for t in result]
        self.assertNotIn(first_tool_name, names)

    def test_context_blocking_all_mcp_prefix(self) -> None:
        from src.tools import PORTED_TOOLS, filter_tools_by_permission_context
        ctx = ToolPermissionContext.from_iterables(deny_prefixes=["mcp"])
        result = filter_tools_by_permission_context(PORTED_TOOLS, ctx)
        for tool in result:
            self.assertFalse(tool.name.lower().startswith("mcp"))

    def test_empty_deny_names_returns_all(self) -> None:
        from src.tools import PORTED_TOOLS, filter_tools_by_permission_context
        ctx = ToolPermissionContext.from_iterables(deny_names=[])
        result = filter_tools_by_permission_context(PORTED_TOOLS, ctx)
        self.assertEqual(len(result), len(PORTED_TOOLS))


# ---------------------------------------------------------------------------
# H10 — PortManifest: custom src_root with temp directory
# Hypothesis: build_port_manifest(src_root=tmpdir) correctly counts only
# Python files in that directory.
# ---------------------------------------------------------------------------
class TestPortManifestCustomRoot(unittest.TestCase):
    """H10: build_port_manifest counts files correctly for custom roots."""

    def test_manifest_with_empty_tempdir_has_zero_files(self) -> None:
        from src.port_manifest import build_port_manifest
        with tempfile.TemporaryDirectory() as tmp:
            manifest = build_port_manifest(src_root=Path(tmp))
        self.assertEqual(manifest.total_python_files, 0)

    def test_manifest_with_one_python_file_counts_one(self) -> None:
        from src.port_manifest import build_port_manifest
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "hello.py").write_text("x = 1")
            manifest = build_port_manifest(src_root=Path(tmp))
        self.assertEqual(manifest.total_python_files, 1)

    def test_manifest_ignores_non_python_files(self) -> None:
        from src.port_manifest import build_port_manifest
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "hello.py").write_text("x = 1")
            (Path(tmp) / "notes.txt").write_text("not python")
            (Path(tmp) / "config.json").write_text("{}")
            manifest = build_port_manifest(src_root=Path(tmp))
        self.assertEqual(manifest.total_python_files, 1)

    def test_manifest_counts_nested_python_files(self) -> None:
        from src.port_manifest import build_port_manifest
        with tempfile.TemporaryDirectory() as tmp:
            sub = Path(tmp) / "submod"
            sub.mkdir()
            (Path(tmp) / "top.py").write_text("")
            (sub / "inner.py").write_text("")
            (sub / "__init__.py").write_text("")
            manifest = build_port_manifest(src_root=Path(tmp))
        self.assertEqual(manifest.total_python_files, 3)

    def test_manifest_to_markdown_mentions_src_root(self) -> None:
        from src.port_manifest import build_port_manifest
        with tempfile.TemporaryDirectory() as tmp:
            manifest = build_port_manifest(src_root=Path(tmp))
        md = manifest.to_markdown()
        self.assertIn("Port root:", md)
        self.assertIn("Total Python files:", md)


# ---------------------------------------------------------------------------
# H11 — ExecutionRegistry: lookup is case-insensitive; missing entries are None
# Hypothesis: registry.command() / registry.tool() use case-insensitive match.
# ---------------------------------------------------------------------------
class TestExecutionRegistryLookup(unittest.TestCase):
    """H11: ExecutionRegistry lookups are case-insensitive and None-safe."""

    def setUp(self) -> None:
        from src.execution_registry import build_execution_registry
        self.registry = build_execution_registry()

    def test_command_lookup_case_insensitive(self) -> None:
        first_name = self.registry.commands[0].name
        self.assertIsNotNone(self.registry.command(first_name.lower()))
        self.assertIsNotNone(self.registry.command(first_name.upper()))

    def test_tool_lookup_case_insensitive(self) -> None:
        first_name = self.registry.tools[0].name
        self.assertIsNotNone(self.registry.tool(first_name.lower()))
        self.assertIsNotNone(self.registry.tool(first_name.upper()))

    def test_missing_command_returns_none(self) -> None:
        self.assertIsNone(self.registry.command("ghost_does_not_exist_xyz"))

    def test_missing_tool_returns_none(self) -> None:
        self.assertIsNone(self.registry.tool("ghost_does_not_exist_xyz"))

    def test_found_command_execute_returns_mirrored_message(self) -> None:
        cmd = self.registry.command(self.registry.commands[0].name)
        self.assertIsNotNone(cmd)
        result = cmd.execute("some input")
        self.assertIn("Mirrored command", result)

    def test_found_tool_execute_returns_mirrored_message(self) -> None:
        tool = self.registry.tool(self.registry.tools[0].name)
        self.assertIsNotNone(tool)
        result = tool.execute("some payload")
        self.assertIn("Mirrored tool", result)


# ---------------------------------------------------------------------------
# H12 — PortingBacklog: summary_lines correctness
# Hypothesis: summary_lines returns one line per module with status and name.
# ---------------------------------------------------------------------------
class TestPortingBacklogSummaryLines(unittest.TestCase):
    """H12: PortingBacklog.summary_lines() format is correct."""

    def test_empty_backlog_returns_empty_list(self) -> None:
        from src.models import PortingBacklog
        backlog = PortingBacklog(title="empty")
        self.assertEqual(backlog.summary_lines(), [])

    def test_summary_lines_count_matches_module_count(self) -> None:
        from src.commands import build_command_backlog
        backlog = build_command_backlog()
        self.assertEqual(len(backlog.summary_lines()), len(backlog.modules))

    def test_each_line_contains_module_name(self) -> None:
        from src.commands import build_command_backlog
        backlog = build_command_backlog()
        for module, line in zip(backlog.modules[:5], backlog.summary_lines()[:5]):
            self.assertIn(module.name, line)

    def test_each_line_contains_status(self) -> None:
        from src.commands import build_command_backlog
        backlog = build_command_backlog()
        for line in backlog.summary_lines()[:5]:
            self.assertIn("[mirrored]", line)


if __name__ == "__main__":
    unittest.main()
