"""Post-run evaluation: start the generated server, check HTTP 200, write run.sh."""

import asyncio
import logging
import os
import stat
from pathlib import Path
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

PORT = 8181
STARTUP_TIMEOUT = 30  # seconds to wait for server to come up
POLL_INTERVAL = 1.0


def _find_entry_point(workspace: Path) -> str | None:
    """Return the command to start the app, or None if we can't figure it out."""
    # Prefer an explicit run.sh the model may have written
    run_sh = workspace / "run.sh"
    if run_sh.exists():
        return f"bash run.sh"

    # Common entry points
    for name in ("app.py", "main.py", "server.py", "web.py"):
        if (workspace / name).exists():
            return f"uv run python {name}"

    # Fall back to any .py file containing 'Flask' or 'app.run'
    for py in workspace.glob("*.py"):
        text = py.read_text(errors="replace")
        if "Flask" in text or "app.run" in text:
            return f"uv run python {py.name}"

    return None


async def _wait_for_port(port: int, timeout: float) -> bool:
    """Poll localhost:port until it accepts connections. Returns True if up."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            _, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.close()
            await writer.wait_closed()
            return True
        except (ConnectionRefusedError, OSError):
            await asyncio.sleep(POLL_INTERVAL)
    return False


async def evaluate(workspace: Path, results_dir: Path) -> dict[str, Any]:
    """
    Try to start the generated server and check it responds with HTTP 200.
    Writes run.sh to results_dir for later manual evaluation.
    Returns an evaluation dict.
    """
    result: dict[str, Any] = {
        "entry_point": None,
        "server_started": False,
        "http_status": None,
        "response_bytes": None,
        "error": None,
    }

    entry_cmd = _find_entry_point(workspace)
    result["entry_point"] = entry_cmd

    if entry_cmd is None:
        logger.warning("No entry point found in workspace")
        result["error"] = "no_entry_point"
        _write_run_sh(results_dir, workspace, None)
        return result

    _write_run_sh(results_dir, workspace, entry_cmd)

    proc = await asyncio.create_subprocess_shell(
        entry_cmd,
        cwd=workspace,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    try:
        up = await _wait_for_port(PORT, STARTUP_TIMEOUT)
        if not up:
            logger.warning("Server did not come up on port %d within %ds", PORT, STARTUP_TIMEOUT)
            result["error"] = "port_never_opened"
            return result

        result["server_started"] = True
        logger.info("Server up on port %d", PORT)

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
                logger.warning("HTTP check failed: %s", exc)
    finally:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()

    return result


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
