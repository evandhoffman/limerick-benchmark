import asyncio
import os
import socket
import subprocess
import sys
import time
import unittest

from benchmark.process_utils import (
    assert_port_available,
    listener_belongs_to_process_tree,
    listener_matches_process_groups,
    port_accepts_connections,
    terminate_process_group,
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_listener(port: int, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_accepts_connections(port):
            return
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for listener on port {port}")


class ProcessUtilsTests(unittest.TestCase):
    def _spawn_listener(self, port: int) -> subprocess.Popen[str]:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-c",
                (
                    "import socket, time; "
                    "sock = socket.socket(); "
                    "sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); "
                    f"sock.bind(('127.0.0.1', {port})); "
                    "sock.listen(); "
                    "time.sleep(60)"
                ),
            ],
            start_new_session=True,
            text=True,
        )
        _wait_for_listener(port)
        return proc

    def test_port_checks_identify_listener_ownership(self) -> None:
        port = _free_port()
        proc = self._spawn_listener(port)
        try:
            with self.assertRaises(RuntimeError):
                assert_port_available(port, "test")
            self.assertTrue(listener_belongs_to_process_tree(port, proc.pid))
            self.assertTrue(listener_matches_process_groups(port, {os.getpgid(proc.pid)}))
            self.assertFalse(listener_matches_process_groups(port, {os.getpgid(proc.pid) + 1}))
        finally:
            asyncio.run(terminate_process_group(proc.pid))
            proc.wait(timeout=5)

    def test_terminate_process_group_kills_listener(self) -> None:
        port = _free_port()
        proc = self._spawn_listener(port)

        asyncio.run(terminate_process_group(proc.pid))
        proc.wait(timeout=5)

        self.assertFalse(port_accepts_connections(port))
