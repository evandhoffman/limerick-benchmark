import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from benchmark.runner import (
    RESULTS_ROOT,
    _new_job_id,
    _prepare_workspace,
    _run_dir,
    _should_evaluate,
    _slug,
    _task_prompt_with_workspace_note,
    _workspace_has_dependency,
    run_benchmark,
)


class RunnerEvaluationPolicyTests(unittest.TestCase):
    def test_skips_evaluation_for_redundant_setup_loop(self) -> None:
        self.assertFalse(_should_evaluate({"finish_reason": "redundant_uv_init_loop", "error": None}))

    def test_skips_evaluation_for_invalid_tool_loop(self) -> None:
        self.assertFalse(_should_evaluate({"finish_reason": "invalid_tool_loop", "error": None}))

    def test_skips_evaluation_for_repeated_command_loop(self) -> None:
        self.assertFalse(_should_evaluate({"finish_reason": "repeated_command_loop", "error": None}))

    def test_skips_evaluation_for_repeated_file_write_loop(self) -> None:
        self.assertFalse(_should_evaluate({"finish_reason": "repeated_file_write_loop", "error": None}))

    def test_skips_evaluation_when_agent_errors(self) -> None:
        self.assertFalse(_should_evaluate({"finish_reason": "error", "error": "boom"}))

    def test_keeps_evaluation_for_timeout(self) -> None:
        self.assertTrue(_should_evaluate({"finish_reason": "timeout", "error": None}))


class RunnerWorkspacePreparationTests(unittest.TestCase):
    def test_prepare_workspace_runs_uv_init_and_adds_flask(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            with mock.patch("benchmark.runner.subprocess.run") as run_mock:
                _prepare_workspace(workspace)

        self.assertEqual(run_mock.call_count, 2)
        init_call = run_mock.call_args_list[0]
        add_call = run_mock.call_args_list[1]
        self.assertEqual(init_call.args[0][:3], ["uv", "init", "."])
        self.assertEqual(add_call.args[0], ["uv", "add", "flask"])
        self.assertEqual(init_call.kwargs["cwd"], workspace)
        self.assertEqual(add_call.kwargs["cwd"], workspace)
        self.assertTrue(init_call.kwargs["check"])
        self.assertTrue(add_call.kwargs["check"])

    def test_prepare_workspace_skips_existing_project(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "pyproject.toml").write_text(
                "[project]\nname='demo'\nversion='0.1.0'\ndependencies=['flask>=3.0']\n"
            )
            with mock.patch("benchmark.runner.subprocess.run") as run_mock:
                _prepare_workspace(workspace)

        run_mock.assert_not_called()

    def test_prepare_workspace_adds_flask_to_existing_project_when_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "pyproject.toml").write_text("[project]\nname='demo'\nversion='0.1.0'\n")
            with mock.patch("benchmark.runner.subprocess.run") as run_mock:
                _prepare_workspace(workspace)

        run_mock.assert_called_once_with(
            ["uv", "add", "flask"],
            cwd=workspace,
            check=True,
            capture_output=True,
            env=mock.ANY,
            text=True,
        )

    def test_task_prompt_includes_workspace_note(self) -> None:
        prompt = _task_prompt_with_workspace_note("Build the app.")
        self.assertIn("already initialized as a uv project", prompt)
        self.assertIn("Do not run `uv init`", prompt)
        self.assertIn("Flask is already installed", prompt)
        self.assertIn("Do not run `uv add flask`", prompt)
        self.assertTrue(prompt.endswith("Build the app."))

    def test_run_dir_nests_model_under_job_id(self) -> None:
        job_id = "20260417.073034"
        run_dir = _run_dir(job_id, "gemma4:e2b")
        self.assertEqual(run_dir, RESULTS_ROOT / job_id / _slug("gemma4:e2b"))
        self.assertEqual(run_dir.parent.name, job_id)
        self.assertNotIn(":", run_dir.name)

    def test_new_job_id_matches_expected_shape(self) -> None:
        job_id = _new_job_id()
        date_part, _, time_part = job_id.partition(".")
        self.assertEqual(len(date_part), 8)
        self.assertEqual(len(time_part), 6)
        self.assertTrue(date_part.isdigit() and time_part.isdigit())

    def test_workspace_has_dependency(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "pyproject.toml").write_text(
                "[project]\nname='demo'\nversion='0.1.0'\ndependencies=['Flask>=3.0']\n"
            )

            self.assertTrue(_workspace_has_dependency(workspace, "flask"))
            self.assertFalse(_workspace_has_dependency(workspace, "rich"))


class RunnerPropagationTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_benchmark_passes_aider_stagnation_timeout_to_each_run(self) -> None:
        model = {"id": "qwen3.5:9b", "provider": "ollama"}
        with TemporaryDirectory() as tmp:
            results_root = Path(tmp) / "results"
            with (
                mock.patch("benchmark.runner.RESULTS_ROOT", results_root),
                mock.patch("benchmark.runner._load_task", return_value="Build the app"),
                mock.patch("benchmark.runner._new_job_id", return_value="20260417.083818"),
                mock.patch(
                    "benchmark.runner._run_one",
                    new=mock.AsyncMock(return_value={"model_id": model["id"]}),
                ) as run_one_mock,
            ):
                summaries = await run_benchmark(
                    [model],
                    agent_type="aider",
                    aider_stagnation_timeout=420,
                )

        self.assertEqual(summaries, [{"model_id": model["id"]}])
        self.assertEqual(
            run_one_mock.await_args.kwargs["aider_stagnation_timeout"],
            420,
        )
