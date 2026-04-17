from types import SimpleNamespace
from unittest import TestCase, mock

import prefetch


class PrefetchTests(TestCase):
    def test_pull_model_uses_subprocess(self) -> None:
        with mock.patch("prefetch.subprocess.run", return_value=SimpleNamespace(returncode=0)) as run_mock:
            self.assertTrue(prefetch.pull_model("gemma4:e2b"))
            run_mock.assert_called_once_with(["ollama", "pull", "gemma4:e2b"])
