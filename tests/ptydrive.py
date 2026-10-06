"""Drive an interactive llgenie in a real pseudo-terminal (stdlib `pty`), the way a
user does: wait for a prompt, type an answer (issue #105)."""
from __future__ import annotations

import os
import pty
import re
import select
import signal
import subprocess
import time


class Pty:
    def __init__(self, argv: list[str], env: dict, cwd: str | None = None):
        self.master, slave = pty.openpty()
        self.proc = subprocess.Popen(argv, stdin=slave, stdout=slave, stderr=slave, env=env, cwd=cwd,
                                     start_new_session=True, close_fds=True)
        os.close(slave)
        self.out = ""

    def _read(self, timeout: float) -> bool:
        r, _, _ = select.select([self.master], [], [], timeout)
        if not r:
            return False
        try:
            chunk = os.read(self.master, 65536).decode(errors="replace")
        except OSError:  # child closed the pty
            return False
        self.out += chunk.replace("\r\n", "\n")
        return bool(chunk)

    def expect(self, pattern: str, timeout: float = 300) -> re.Match:
        end = time.time() + timeout
        rx = re.compile(pattern)
        while time.time() < end:
            m = rx.search(self.out)
            if m:
                return m
            if not self._read(1) and self.proc.poll() is not None:
                while self._read(0.2):
                    pass
                m = rx.search(self.out)
                if m:
                    return m
                raise AssertionError(f"exited {self.proc.returncode} before {pattern!r}:\n{self.out[-4000:]}")
        raise AssertionError(f"timeout waiting for {pattern!r}:\n{self.out[-4000:]}")

    def send(self, line: str) -> None:
        os.write(self.master, (line + "\n").encode())

    def wait(self, timeout: float = 300) -> int:
        end = time.time() + timeout
        while self.proc.poll() is None and time.time() < end:
            self._read(0.5)
        while self._read(0.2):
            pass
        if self.proc.poll() is None:
            self.close()
            raise AssertionError(f"still running after {timeout}s:\n{self.out[-4000:]}")
        return self.proc.returncode

    def close(self) -> None:
        if self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
                self.proc.wait(timeout=30)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                os.killpg(self.proc.pid, signal.SIGKILL)
        try:
            os.close(self.master)
        except OSError:
            pass
