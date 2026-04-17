"""Helpers for port ownership checks and subprocess cleanup."""

from __future__ import annotations

import asyncio
import os
import signal
import socket
import subprocess
from typing import Iterable

import psutil


def listening_pids(port: int) -> set[int]:
    """Return PIDs of processes listening on the given TCP port."""
    pids: set[int] = set()
    try:
        connections = psutil.net_connections(kind="tcp")
    except psutil.Error:
        connections = []

    for conn in connections:
        if conn.status != psutil.CONN_LISTEN or not conn.laddr or conn.pid is None:
            continue
        if conn.laddr.port == port:
            pids.add(conn.pid)

    if pids:
        return pids

    try:
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return pids

    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.add(int(line))
    return pids


def port_accepts_connections(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    """Return True if a TCP connection succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def assert_port_available(port: int, context: str) -> None:
    """Raise if the benchmark port is already occupied."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            pids = sorted(listening_pids(port))
            pid_suffix = f" Listening PIDs: {pids}." if pids else ""
            raise RuntimeError(f"Port {port} is already in use before {context}.{pid_suffix}") from exc


def process_tree_pids(root_pid: int) -> set[int]:
    """Return the root process and all recursive child PIDs."""
    try:
        root = psutil.Process(root_pid)
    except psutil.Error:
        return set()

    pids = {root_pid}
    for child in root.children(recursive=True):
        pids.add(child.pid)
    return pids


def listener_belongs_to_process_tree(port: int, root_pid: int) -> bool:
    """Return True if a listener on port belongs to the given process tree."""
    return bool(listening_pids(port) & process_tree_pids(root_pid))


def listener_matches_process_groups(port: int, process_groups: Iterable[int]) -> bool:
    """Return True if any listener on port is in one of the given process groups."""
    tracked = set(process_groups)
    if not tracked:
        return False

    for pid in listening_pids(port):
        try:
            if os.getpgid(pid) in tracked:
                return True
        except ProcessLookupError:
            continue
    return False


def process_group_exists(pgid: int) -> bool:
    """Return True if the process group still exists."""
    return bool(process_group_pids(pgid))


def process_group_pids(pgid: int) -> set[int]:
    """Return the current PIDs in a process group."""
    members: set[int] = set()
    for proc in psutil.process_iter(["pid"]):
        pid = proc.info["pid"]
        try:
            if os.getpgid(pid) == pgid:
                members.add(pid)
        except (ProcessLookupError, PermissionError):
            continue
    return members


async def terminate_process_group(pgid: int, grace_seconds: float = 5.0) -> None:
    """Terminate a process group and escalate to SIGKILL if needed."""
    pids = process_group_pids(pgid)
    if not pids:
        return

    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            continue

    deadline = asyncio.get_running_loop().time() + grace_seconds
    while process_group_exists(pgid) and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.1)

    for pid in process_group_pids(pgid):
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            continue


async def terminate_process_groups(process_groups: Iterable[int], grace_seconds: float = 5.0) -> None:
    """Terminate every tracked process group."""
    for pgid in sorted(set(process_groups)):
        await terminate_process_group(pgid, grace_seconds=grace_seconds)
