# Repository Guidelines

## Project Structure & Module Organization
`benchmark/` contains the runtime code: `__main__.py` exposes the CLI, `runner.py` orchestrates serial model runs, `agent.py` manages the tool-calling loop, and `evaluator.py` validates generated apps. `prefetch.py` is a separate CLI for pulling Ollama models. Benchmark inputs live in `tasks/` and `models.yaml`. Run artifacts are written to `results/`; each result directory links to a generated workspace under `~/.limerick-benchmark/workspaces/`.

## Build, Test, and Development Commands
Use `uv` for all Python workflows.

- `uv sync` installs project dependencies from `pyproject.toml` and `uv.lock`.
- `uv run benchmark list` shows locally available Ollama models and catalog membership.
- `uv run benchmark run --set poc` runs the smallest proof-of-concept benchmark set.
- `uv run benchmark run --model gemma4:e2b` runs a single model.
- `uv run prefetch --set recommended --dry-run` previews required Ollama downloads.
- `uv run python -m benchmark run --set local` is the module-form equivalent if you are debugging imports.

## Coding Style & Naming Conventions
Target Python 3.11+ and keep code stdlib-first unless a dependency is already declared. Follow existing style: 4-space indentation, snake_case for functions and variables, CapWords for classes, and explicit type hints on public helpers. Keep modules focused; new benchmark pipeline logic belongs in `benchmark/`, not top-level scripts. There is no committed formatter or linter config yet, so match the surrounding style and keep imports/readability clean.

## Testing Guidelines
There is no dedicated `tests/` package yet. For changes, rely on targeted command-level verification and document what you ran in the PR. At minimum, exercise the affected CLI path with `uv run benchmark ...` or `uv run prefetch ...`. If you add automated coverage, prefer `tests/test_*.py` and `pytest`, and keep fixtures small because benchmark runs are expensive.

## Commit & Pull Request Guidelines
Recent commits use short, imperative subjects such as `Fix UnboundLocalError...` and `Stream model output live...`. Follow that pattern: lead with the action, keep the summary specific, and avoid noisy prefixes. PRs should explain the behavioral change, list verification commands, and note any environment assumptions (`ollama serve`, `ANTHROPIC_API_KEY`, `sudo powermetrics`). Include sample `results/` output or screenshots only when UI or evaluation behavior changes.

## Environment & Safety Notes
This project assumes macOS on Apple Silicon. Do not commit generated workspaces or large benchmark artifacts. Treat `models.yaml` edits carefully: they affect benchmark selection, download size, and reproducibility.
