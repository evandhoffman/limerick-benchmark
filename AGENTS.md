# Repository Guidelines

This file is the single source of instructions for any coding agent working in
this repo. `CLAUDE.md` and `GEMINI.md` are symlinks to this file, so Claude
Code, Codex, Gemini, and Aider all read the same guidance. **Edit `AGENTS.md`
directly** — do not create per-agent variants.

## Project Structure & Module Organization
`benchmark/` contains the core runtime code:
- `__main__.py`: CLI entry point (`uv run benchmark {list,run}`). Parses args,
  loads `models.yaml`, runs the preflight table, dispatches to `runner`.
- `runner.py`: Orchestrates serial model runs, prepares each workspace under
  `~/.limerick-benchmark/workspaces/<timestamp>_<slug>/`, and writes artifacts
  to `results/<timestamp>_<slug>/` (symlinked to the workspace).
- `agent.py`: Hosts both agent backends.
  - ReAct loop using `litellm` with a single `bash` tool (60 s per-command
    timeout, 15-minute overall hard limit). Loop-detection guards cover
    repeated commands, redundant `uv init`, and repeated full-file rewrites.
  - `_run_aider` wraps the Aider CLI (`--agent aider`) with a sliding-window
    log-line repeat detector.
- `evaluator.py`: Starts the generated app and validates it against the task
  requirements (HTTP 200 on port 8181 for the limerick task).
- `metrics.py`: Background 5 s sampler for CPU/memory and — when
  `--enable-hardware-metrics` is set — GPU, thermals, and fan RPM via
  `powermetrics` (requires `sudo`).
- `ollama_utils.py`: Local Ollama model store helpers.
- `process_utils.py`: Port ownership checks and subprocess cleanup.

`prefetch.py` is a separate CLI for pulling Ollama models. Benchmark inputs
live in `tasks/` (Markdown files, currently `limerick.md`) and `models.yaml`
(the model catalog with `poc`/`v1`/`recommended`/`exclude` flags).

Generated workspaces live **outside** the repo tree at
`~/.limerick-benchmark/workspaces/` so `uv init` inside them cannot walk up
and auto-register as a member of this project's `pyproject.toml`. Never move
them back under the repo.

## Build, Test, and Development Commands
Use `uv` for all Python workflows — never call `pip`/`python` directly.

- `uv sync`: Install dependencies from `pyproject.toml` / `uv.lock`.
- `uv run benchmark list`: Show locally-pulled Ollama models vs. the catalog.
- `uv run benchmark run --set poc`: Smallest proof-of-concept run.
- `uv run benchmark run --set recommended --skip-missing`: Full run, skipping
  models that aren't pulled.
- `uv run benchmark run --model gemma4:e2b`: Single model.
- `uv run benchmark run --set poc --agent aider`: Use the Aider agent instead
  of the default ReAct loop.
- `uv run benchmark run --set poc --enable-hardware-metrics`: Include GPU /
  thermal / fan metrics (prompts for `sudo`).
- `uv run prefetch --set recommended --dry-run`: Preview required downloads.
- `uv run python -m unittest discover tests`: Run the test suite.

## Coding Style & Naming Conventions
Target Python 3.11+ and keep code stdlib-first unless a dependency (like
`litellm`, `rich`, or `pyyaml`) is already declared. 4-space indentation,
snake_case for functions/variables, CapWords for classes, explicit type hints
on public helpers. Keep modules focused; new benchmark pipeline logic belongs
in `benchmark/`, not top-level scripts.

Use the `logging` module (`logger = logging.getLogger(__name__)`) for all
output. Do not use `print()` in library code; `rich.console` is acceptable for
user-facing CLI tables in `__main__.py`.

## Testing Guidelines
The `tests/` directory contains `unittest` suites mirroring the `benchmark/`
modules (`test_agent.py`, `test_runner.py`, `test_evaluator.py`,
`test_metrics.py`, `test_process_utils.py`, `test_prefetch.py`). For any
change, add or update a test case. Run the full suite with
`uv run python -m unittest discover tests` before submitting. At minimum,
exercise the affected CLI path with `uv run benchmark ...` or
`uv run prefetch ...`.

## Commit & Pull Request Guidelines
Recent commits use short, imperative subjects such as
`Add infinite loop detection to Aider agent` and
`Stream model output live...`. Lead with the action, keep the summary
specific, no noisy prefixes. PRs should explain the behavioral change, list
verification commands, and note any environment assumptions
(`ollama serve`, `ANTHROPIC_API_KEY`, `sudo powermetrics`).

## Environment & Safety Notes
This project assumes macOS on Apple Silicon. Do not commit generated
workspaces, `results/` artifacts, or large binaries. Treat `models.yaml`
edits carefully: they affect benchmark selection, download size, and
reproducibility. The agent loop runs arbitrary shell commands from model
output — only run it inside workspaces under
`~/.limerick-benchmark/workspaces/` and never in the repo root.
