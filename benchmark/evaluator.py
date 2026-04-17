"""Post-run evaluation: start the generated server, check HTTP 200, write run.sh."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import stat
import tomllib
from pathlib import Path
from typing import Any

import aiohttp

from .process_utils import (
    assert_port_available,
    listener_belongs_to_process_tree,
    sanitized_subprocess_env,
    terminate_process_group,
)

logger = logging.getLogger(__name__)

PORT = 8181
STARTUP_TIMEOUT = 30  # seconds to wait for server to come up
POLL_INTERVAL = 1.0


def _script_commands_from_pyproject(workspace: Path) -> list[str]:
    pyproject = workspace / "pyproject.toml"
    if not pyproject.exists():
        return []

    try:
        data = tomllib.loads(pyproject.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return []

    scripts = data.get("project", {}).get("scripts", {})
    if not isinstance(scripts, dict):
        return []
    return [f"uv run {name}" for name in scripts]


def _candidate_entry_points(workspace: Path) -> list[str]:
    """Return plausible commands to start the generated app."""
    candidates: list[str] = []

    def add(command: str) -> None:
        if command not in candidates:
            candidates.append(command)

    run_sh = workspace / "run.sh"
    if run_sh.exists():
        add("bash run.sh")

    for command in _script_commands_from_pyproject(workspace):
        add(command)

    search_roots = [workspace]
    src_dir = workspace / "src"
    if src_dir.exists():
        search_roots.append(src_dir)

    for root in search_roots:
        for name in ("app.py", "main.py", "server.py", "web.py"):
            py = root / name
            if py.exists():
                add(f"uv run python {py.relative_to(workspace)}")

        for package_main in sorted(root.glob("*/__main__.py")):
            package_dir = package_main.parent
            if not package_dir.name.isidentifier():
                continue
            if root == src_dir:
                add(f"uv run python -m {package_dir.name}")
            else:
                module = package_dir.relative_to(workspace).as_posix().replace("/", ".")
                add(f"uv run python -m {module}")

        python_files = sorted(root.glob("*.py"))
        for py in python_files:
            text = py.read_text(errors="replace")
            if "Flask" in text or "app.run" in text:
                add(f"uv run python {py.relative_to(workspace)}")

        if len(python_files) == 1:
            add(f"uv run python {python_files[0].relative_to(workspace)}")

    return candidates


async def _wait_for_port(port: int, timeout: float) -> bool:
    """Poll localhost:port until it accepts connections. Returns True if up."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        try:
            _, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.close()
            await writer.wait_closed()
            return True
        except (ConnectionRefusedError, OSError):
            await asyncio.sleep(POLL_INTERVAL)
    return False


async def _try_entry_point(workspace: Path, entry_cmd: str) -> dict[str, Any]:
    """Start one candidate entry point and return the evaluation result."""
    assert_port_available(PORT, f"starting evaluator command '{entry_cmd}'")

    result: dict[str, Any] = {
        "entry_point": entry_cmd,
        "server_started": False,
        "http_status": None,
        "response_bytes": None,
        "error": None,
    }

    proc = await asyncio.create_subprocess_shell(
        entry_cmd,
        cwd=workspace,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        env=sanitized_subprocess_env(),
        start_new_session=True,
    )

    try:
        up = await _wait_for_port(PORT, STARTUP_TIMEOUT)
        if not up:
            logger.warning("Server did not come up on port %d within %ds for '%s'", PORT, STARTUP_TIMEOUT, entry_cmd)
            result["error"] = "port_never_opened"
            return result

        if not listener_belongs_to_process_tree(PORT, proc.pid):
            logger.warning("Port %d listener was not started by '%s'", PORT, entry_cmd)
            result["error"] = "unexpected_listener"
            return result

        result["server_started"] = True
        logger.info("Server up on port %d via '%s'", PORT, entry_cmd)

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"http://localhost:{PORT}/",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    body = await resp.read()
                    result["http_status"] = resp.status
                    result["response_bytes"] = len(body)
                    logger.info("GET / → %d (%d bytes)", resp.status, len(body))
            except Exception as exc:
                result["error"] = f"http_error: {exc}"
                logger.warning("HTTP check failed for '%s': %s", entry_cmd, exc)
    finally:
        await terminate_process_group(proc.pid)
        with contextlib.suppress(RuntimeError):
            assert_port_available(PORT, f"cleaning up evaluator command '{entry_cmd}'")

    return result


async def evaluate(workspace: Path, results_dir: Path) -> dict[str, Any]:
    """
    Try to start the generated server and check it responds with HTTP 200.
    Writes run.sh to results_dir for later manual evaluation.
    Returns an evaluation dict.
    """
    entry_points = _candidate_entry_points(workspace)
    if not entry_points:
        logger.warning("No entry point found in workspace")
        result = {
            "entry_point": None,
            "entry_point_candidates": [],
            "server_started": False,
            "http_status": None,
            "response_bytes": None,
            "error": "no_entry_point",
        }
        _write_run_sh(results_dir, workspace, None)
        return result

    last_result: dict[str, Any] = {
        "entry_point": entry_points[0],
        "entry_point_candidates": entry_points,
        "server_started": False,
        "http_status": None,
        "response_bytes": None,
        "error": "port_never_opened",
    }

    for entry_cmd in entry_points:
        candidate_result = await _try_entry_point(workspace, entry_cmd)
        candidate_result["entry_point_candidates"] = entry_points
        last_result = candidate_result
        if candidate_result.get("http_status") == 200:
            _write_run_sh(results_dir, workspace, entry_cmd)
            return candidate_result

    _write_run_sh(results_dir, workspace, last_result.get("entry_point"))
    return last_result


def _write_run_sh(results_dir: Path, workspace: Path, entry_cmd: str | None) -> None:
    """Write a convenience run.sh to the results directory."""
    run_sh = results_dir / "run.sh"
    if entry_cmd:
        content = f"#!/bin/sh\ncd '{workspace}'\n{entry_cmd}\n"
    else:
        content = (
            "#!/bin/sh\n"
            "# No entry point was detected — inspect the workspace manually.\n"
            f"echo 'Workspace: {workspace}'\n"
            f"ls '{workspace}'\n"
        )
    run_sh.write_text(content)
    run_sh.chmod(run_sh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
