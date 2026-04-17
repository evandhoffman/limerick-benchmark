# Repository Guidelines

## Project Structure & Module Organization
`benchmark/` contains the core runtime code:
- `__main__.py`: Exposes the main CLI (`uv run benchmark`).
- `runner.py`: Orchestrates serial model runs across the catalog.
- `agent.py`: Manages the ReAct tool-calling loop using `litellm`.
- `evaluator.py`: Validates generated applications against requirements.
- `metrics.py`: Background system metrics collector (CPU, GPU, thermals via `powermetrics`).
- `ollama_utils.py`: Shared helpers for querying the local Ollama model store.
- `process_utils.py`: Port ownership checks and subprocess cleanup.

`prefetch.py` is a separate CLI for pulling Ollama models. Benchmark inputs live in `tasks/` (Markdown files) and `models.yaml` (the model catalog). Run artifacts are written to `results/`; each result directory links to a generated workspace under `~/.limerick-benchmark/workspaces/`.

## Build, Test, and Development Commands
Use `uv` for all Python workflows.

- `uv sync`: Installs project dependencies from `pyproject.toml` and `uv.lock`.
- `uv run benchmark list`: Shows locally available Ollama models and catalog membership.
- `uv run benchmark run --set poc`: Runs the smallest proof-of-concept benchmark set.
- `uv run benchmark run --model gemma4:e2b`: Runs a single model.
- `uv run prefetch --set recommended --dry-run`: Previews required Ollama downloads.
- `uv run python -m unittest discover tests`: Runs the project's test suite.

## Coding Style & Naming Conventions
Target Python 3.11+ and keep code stdlib-first unless a dependency (like `litellm` or `rich`) is already declared. Follow existing style: 4-space indentation, snake_case for functions and variables, CapWords for classes, and explicit type hints on public helpers. Keep modules focused; new benchmark pipeline logic belongs in `benchmark/`, not top-level scripts.

## Testing Guidelines
The `tests/` directory contains `unittest` test suites for core modules. For any change, you must add or update a test case in `tests/`. Run all tests with `uv run python -m unittest discover tests` before submitting. At minimum, exercise the affected CLI path with `uv run benchmark ...` or `uv run prefetch ...`.

## Commit & Pull Request Guidelines
Recent commits use short, imperative subjects such as `Fix UnboundLocalError...` and `Stream model output live...`. Follow that pattern: lead with the action, keep the summary specific, and avoid noisy prefixes. PRs should explain the behavioral change, list verification commands, and note any environment assumptions (`ollama serve`, `ANTHROPIC_API_KEY`, `sudo powermetrics`).

## Environment & Safety Notes
This project assumes macOS on Apple Silicon. Do not commit generated workspaces or large benchmark artifacts. Treat `models.yaml` edits carefully: they affect benchmark selection, download size, and reproducibility.
