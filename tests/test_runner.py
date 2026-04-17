import json
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
    def test_prepare_workspace_is_a_noop_without_task_resources(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            _prepare_workspace(workspace)
            self.assertEqual(list(workspace.iterdir()), [])

    def test_prepare_workspace_seeds_limericks_file(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            tasks_dir = root / "tasks"
            tasks_dir.mkdir()
            (tasks_dir / "limericks.txt").write_text("seed\n")

            with mock.patch("benchmark.runner.TASKS_DIR", tasks_dir):
                _prepare_workspace(workspace, task_name="limerick")

            self.assertEqual((workspace / "limericks.txt").read_text(), "seed\n")

    def test_task_prompt_includes_workspace_note(self) -> None:
        prompt = _task_prompt_with_workspace_note("Build the app.", task_name="limerick")
        self.assertIn("responsible for setting", prompt)
        self.assertIn("`app.py`", prompt)
        self.assertIn("limericks.txt", prompt)
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
                mock.patch(
                    "benchmark.runner.write_markdown_report",
                    return_value=Path(tmp) / "reports" / "results_20260417.083818.md",
                ),
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

    async def test_run_benchmark_writes_job_metadata_and_generates_report(self) -> None:
        model = {"id": "gemma4:e2b", "provider": "ollama"}
        with TemporaryDirectory() as tmp:
            results_root = Path(tmp) / "results"
            report_path = Path(tmp) / "reports" / "results_20260417.083818.md"
            with (
                mock.patch("benchmark.runner.RESULTS_ROOT", results_root),
                mock.patch("benchmark.runner._load_task", return_value="Build the app"),
                mock.patch("benchmark.runner._new_job_id", return_value="20260417.083818"),
                mock.patch(
                    "benchmark.runner._run_one",
                    new=mock.AsyncMock(return_value={"model_id": model["id"]}),
                ),
                mock.patch(
                    "benchmark.runner.write_markdown_report",
                    return_value=report_path,
                ) as write_report_mock,
            ):
                await run_benchmark(
                    [model],
                    task_name="limerick",
                    agent_type="react",
                    timeout=600,
                    aider_stagnation_timeout=420,
                    enable_hardware_metrics=True,
                )

            job_metadata = json.loads((results_root / "20260417.083818" / "job.json").read_text())
            self.assertEqual(job_metadata["job_id"], "20260417.083818")
            self.assertEqual(job_metadata["task_name"], "limerick")
            self.assertEqual(job_metadata["agent_type"], "react")
            self.assertEqual(job_metadata["timeout_seconds"], 600)
            self.assertEqual(job_metadata["aider_stagnation_timeout_seconds"], 420)
            self.assertTrue(job_metadata["enable_hardware_metrics"])
            self.assertEqual(job_metadata["model_ids"], ["gemma4:e2b"])
            write_report_mock.assert_called_once_with(results_root / "20260417.083818")
