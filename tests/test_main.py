import sys
import unittest
from unittest import mock

import benchmark.__main__ as benchmark_main
from benchmark.agent import AIDER_STAGNATION_SECONDS


class MainCliTests(unittest.TestCase):
    def test_run_uses_default_aider_stagnation_timeout(self) -> None:
        with (
            mock.patch("benchmark.__main__.load_catalog", return_value={}),
            mock.patch("benchmark.__main__.get_pulled_names", return_value=set()),
            mock.patch("benchmark.__main__.preflight_check", return_value=True),
            mock.patch(
                "benchmark.__main__.run_benchmark",
                new=mock.Mock(return_value=[]),
            ) as run_benchmark_mock,
            mock.patch("benchmark.__main__.asyncio.run", return_value=[]),
            mock.patch.object(sys, "argv", ["benchmark", "run", "--model", "gemma4:e2b"]),
        ):
            benchmark_main.main()

        self.assertEqual(
            run_benchmark_mock.call_args.kwargs["aider_stagnation_timeout"],
            AIDER_STAGNATION_SECONDS,
        )

    def test_run_accepts_explicit_aider_stagnation_timeout_flag(self) -> None:
        with (
            mock.patch("benchmark.__main__.load_catalog", return_value={}),
            mock.patch("benchmark.__main__.get_pulled_names", return_value=set()),
            mock.patch("benchmark.__main__.preflight_check", return_value=True),
            mock.patch(
                "benchmark.__main__.run_benchmark",
                new=mock.Mock(return_value=[]),
            ) as run_benchmark_mock,
            mock.patch("benchmark.__main__.asyncio.run", return_value=[]),
            mock.patch.object(
                sys,
                "argv",
                [
                    "benchmark",
                    "run",
                    "--model",
                    "gemma4:e2b",
                    "--agent",
                    "aider",
                    "--aider-stagnation-timeout",
                    "420",
                ],
            ),
        ):
            benchmark_main.main()

        self.assertEqual(
            run_benchmark_mock.call_args.kwargs["aider_stagnation_timeout"],
            420,
        )
