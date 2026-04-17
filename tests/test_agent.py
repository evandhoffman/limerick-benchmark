import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from benchmark.agent import (
    AIDER_STAGNATION_SECONDS,
    _aider_has_repeating_cycle,
    _aider_low_uniqueness,
    _declared_dependencies,
    _contains_redundant_uv_init,
    _detect_aider_terminal_issue,
    _extract_aider_edit_target,
    _format_status_line,
    _hash_workspace_tree,
    _normalize_aider_line,
    _normalize_dependency_name,
    _parse_aider_token_usage,
    _parse_tool_arguments,
    _prepare_command,
    run_agent,
    _summarize_command_output,
    _workspace_has_started_work,
    _written_file_target,
)


class ParseToolArgumentsTests(unittest.TestCase):
    def test_rejects_invalid_json(self) -> None:
        with self.assertRaises(ValueError):
            _parse_tool_arguments('{"command": ')

    def test_rejects_non_object_json(self) -> None:
        with self.assertRaises(ValueError):
            _parse_tool_arguments('["pwd"]')

    def test_accepts_valid_object_json(self) -> None:
        self.assertEqual(_parse_tool_arguments('{"command": "pwd"}'), {"command": "pwd"})


class AgentConsoleFormattingTests(unittest.TestCase):
    def test_formats_compact_status_line(self) -> None:
        line = _format_status_line(
            "ollama_chat/qwen3.5:9b",
            elapsed_s=134.0,
            phase="thinking",
            api_calls=3,
            tool_calls=7,
            output_tokens=1842,
            tokens_per_second=21.6,
        )

        self.assertIn("[ollama_chat/qwen3.5:9b] 02:14 | thinking", line)
        self.assertIn("api=3 tool=7", line)
        self.assertIn("1842", line)
        self.assertIn("21.6 tok/s", line)

    def test_summarizes_multiline_command_output(self) -> None:
        summary = _summarize_command_output("line one\nline two\nline three\n")
        self.assertIn("3 lines", summary)
        self.assertIn("line one", summary)

    def test_preserves_short_single_line_output(self) -> None:
        self.assertEqual(_summarize_command_output("installed"), "installed")


class AgentWorkspaceDetectionTests(unittest.TestCase):
    def test_empty_workspace_is_not_started(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertFalse(_workspace_has_started_work(Path(tmp)))

    def test_initialized_workspace_counts_as_started_without_python_files(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "pyproject.toml").write_text("[project]\nname='demo'\nversion='0.1.0'\n")
            self.assertTrue(_workspace_has_started_work(workspace))

    def test_prepare_command_skips_redundant_uv_init(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "pyproject.toml").write_text("[project]\nname='demo'\nversion='0.1.0'\n")

            command, note = _prepare_command("uv init .\nuv add flask", workspace)

        self.assertEqual(command, "uv add flask")
        self.assertIn("skipped redundant `uv init`", note)

    def test_prepare_command_returns_note_when_only_uv_init_remains(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "pyproject.toml").write_text("[project]\nname='demo'\nversion='0.1.0'\n")

            command, note = _prepare_command("uv init .", workspace)

        self.assertIsNone(command)
        self.assertIn("Do not run `uv init` again", note)

    def test_detects_redundant_uv_init_only_after_initialization(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.assertFalse(_contains_redundant_uv_init("uv init .", workspace))
            (workspace / "pyproject.toml").write_text("[project]\nname='demo'\nversion='0.1.0'\n")
            self.assertTrue(_contains_redundant_uv_init("uv init .", workspace))

    def test_prepare_command_skips_redundant_uv_add(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "pyproject.toml").write_text(
                "[project]\nname='demo'\nversion='0.1.0'\ndependencies=['flask>=3.0']\n"
            )

            command, note = _prepare_command("uv add flask", workspace)

        self.assertIsNone(command)
        self.assertIn("skipped redundant `uv add`", note)

    def test_declared_dependencies_normalize_names(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "pyproject.toml").write_text(
                "[project]\nname='demo'\nversion='0.1.0'\ndependencies=['Flask[async]>=3.0; python_version >= \"3.11\"']\n"
            )

            deps = _declared_dependencies(workspace)

        self.assertEqual(deps, {"flask"})

    def test_normalize_dependency_name(self) -> None:
        self.assertEqual(_normalize_dependency_name("Flask[async]>=3.0"), "flask")

    def test_written_file_target_detects_redirect_target(self) -> None:
        self.assertEqual(_written_file_target("cat <<EOF > app.py\nhello\nEOF"), "app.py")
        self.assertEqual(_written_file_target("printf foo > src/app.py"), "src/app.py")
        self.assertIsNone(_written_file_target("uv run python app.py"))


class AiderLoopDetectionTests(unittest.TestCase):
    def test_normalize_strips_ansi_numbers_and_paths(self) -> None:
        line = "\x1b[31mApplied edit to /tmp/abc123/app.py at 12:34:56 (1234 tokens)\x1b[0m"
        normalized = _normalize_aider_line(line)
        self.assertNotIn("\x1b", normalized)
        self.assertNotIn("1234", normalized)
        self.assertIn("<path>", normalized)
        self.assertIn("<n>", normalized)

    def test_normalize_masks_near_duplicates_across_runs(self) -> None:
        a = _normalize_aider_line("Retrying app.py (attempt 3 of 5)")
        b = _normalize_aider_line("Retrying app.py (attempt 4 of 5)")
        self.assertEqual(a, b)

    def test_low_uniqueness_returns_false_before_window_full(self) -> None:
        self.assertFalse(_aider_low_uniqueness(["a", "b", "c"], window=60, threshold=8))

    def test_low_uniqueness_trips_when_few_unique_lines(self) -> None:
        lines = (["x", "y"] * 30)[-60:]
        self.assertTrue(_aider_low_uniqueness(lines, window=60, threshold=8))

    def test_low_uniqueness_accepts_varied_output(self) -> None:
        lines = [f"line-{i}" for i in range(60)]
        self.assertFalse(_aider_low_uniqueness(lines, window=60, threshold=8))

    def test_cycle_detection_trips_on_repeating_block(self) -> None:
        block = ["thinking", "editing app.py", "running tests", "failure"]
        lines = block * 3
        self.assertTrue(_aider_has_repeating_cycle(lines, min_period=2, max_period=10, min_repeats=3))

    def test_cycle_detection_ignores_non_repeating_tail(self) -> None:
        lines = [f"step-{i}" for i in range(30)]
        self.assertFalse(_aider_has_repeating_cycle(lines))

    def test_extract_aider_edit_target_matches_common_patterns(self) -> None:
        self.assertEqual(_extract_aider_edit_target("Applied edit to app.py"), "app.py")
        self.assertEqual(_extract_aider_edit_target("Edited src/app.py."), "src/app.py")
        self.assertEqual(_extract_aider_edit_target("Wrote changes to tests/test_app.py"), "tests/test_app.py")
        self.assertIsNone(_extract_aider_edit_target("Thinking about the problem..."))

    def test_workspace_hash_changes_with_content_and_ignores_caches(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "app.py").write_text("print('hi')\n")
            cache_dir = workspace / "__pycache__"
            cache_dir.mkdir()
            (cache_dir / "noise.pyc").write_bytes(b"\x00" * 16)
            (workspace / ".aider.chat.history.md").write_text("noise")

            h1 = _hash_workspace_tree(workspace)

            (cache_dir / "noise.pyc").write_bytes(b"\x00" * 32)
            (workspace / ".aider.chat.history.md").write_text("different noise")
            self.assertEqual(h1, _hash_workspace_tree(workspace))

            (workspace / "app.py").write_text("print('bye')\n")
            self.assertNotEqual(h1, _hash_workspace_tree(workspace))

    def test_detects_aider_edit_format_reject_from_log_stream(self) -> None:
        issue = _detect_aider_terminal_issue(
            [
                "The LLM did not conform to the edit format.",
                "https://aider.chat/docs/troubleshooting/edit-errors.html",
                "No filename provided before ``` in file listing",
                "Only 3 reflections allowed, stopping.",
            ]
        )

        self.assertIsNotNone(issue)
        category, detail = issue or ("", "")
        self.assertEqual(category, "aider_edit_format_reject")
        self.assertIn("The LLM did not conform to the edit format.", detail)
        self.assertIn("No filename provided before ``` in file listing", detail)

    def test_parses_aider_token_usage_summary(self) -> None:
        self.assertEqual(
            _parse_aider_token_usage("Tokens: 5.2k sent, 820 received."),
            (5200, 820),
        )
        self.assertEqual(
            _parse_aider_token_usage("Tokens: 12,400 sent, 1.3k received."),
            (12400, 1300),
        )
        self.assertIsNone(_parse_aider_token_usage("Cost: $0.02"))


class AiderConfigurationTests(unittest.TestCase):
    def test_default_stagnation_timeout_is_300_seconds(self) -> None:
        self.assertEqual(AIDER_STAGNATION_SECONDS, 300)


class RunAgentDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_aider_path_receives_stagnation_timeout(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            trace_path = workspace / "trace.jsonl"
            with mock.patch(
                "benchmark.agent._run_aider",
                new=mock.AsyncMock(return_value={"finish_reason": "completed"}),
            ) as aider_mock:
                result = await run_agent(
                    model_id="qwen3.5:9b",
                    provider="ollama",
                    task_prompt="Build the app",
                    workspace=workspace,
                    trace_path=trace_path,
                    token_state={},
                    timeout=900,
                    aider_stagnation_timeout=420,
                    agent_type="aider",
                    run_label="1/1:qwen3.5-9b:aider",
                )

        self.assertEqual(result, {"finish_reason": "completed"})
        self.assertEqual(
            aider_mock.await_args.kwargs["aider_stagnation_timeout"],
            420,
        )

    async def test_react_path_accepts_default_aider_stagnation_timeout(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            trace_path = workspace / "trace.jsonl"
            with mock.patch(
                "benchmark.agent._run_react",
                new=mock.AsyncMock(return_value={"finish_reason": "completed"}),
            ) as react_mock:
                await run_agent(
                    model_id="qwen3.5:9b",
                    provider="ollama",
                    task_prompt="Build the app",
                    workspace=workspace,
                    trace_path=trace_path,
                    token_state={},
                    agent_type="react",
                )

        self.assertEqual(react_mock.await_args.kwargs["timeout"], 900)
