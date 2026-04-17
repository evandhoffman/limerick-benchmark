import tempfile
import unittest
from pathlib import Path

from benchmark.evaluator import _candidate_entry_points


class CandidateEntryPointTests(unittest.TestCase):
    def test_discovers_project_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "pyproject.toml").write_text(
                "[project]\n"
                "name = 'demo'\n"
                "version = '0.1.0'\n"
                "[project.scripts]\n"
                "serve-demo = 'demo:main'\n"
            )

            self.assertIn("uv run serve-demo", _candidate_entry_points(workspace))

    def test_discovers_src_package_main_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            package_dir = workspace / "src" / "demoapp"
            package_dir.mkdir(parents=True)
            (package_dir / "__main__.py").write_text("print('hello')\n")

            self.assertIn("uv run python -m demoapp", _candidate_entry_points(workspace))

    def test_discovers_src_flask_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            src_dir = workspace / "src"
            src_dir.mkdir()
            (src_dir / "server.py").write_text("from flask import Flask\napp = Flask(__name__)\n")

            self.assertIn("uv run python src/server.py", _candidate_entry_points(workspace))
