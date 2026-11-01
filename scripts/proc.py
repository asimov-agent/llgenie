#!/usr/bin/env python3
"""The ONE subprocess policy seam for scripts/ (issue #797).

Before this module, ~30 scripts defined their own subprocess helper under five spellings
(`_run`, `_sh`, `_gh`, `run_gh`, `_cmd`) and disagreed on the only thing that matters — what a
non-zero exit does. Eleven never inspected `.returncode` (the failure was dropped), and two of those
turned a failed command into `""` (`detect_server._run`, `engine_skills._run`), which version/hardware
detection reads as the benign "no version" branch.

This module is that disagreement collapsed into three named policies. A caller states its policy by
naming the function — there is NO policy default and no `_run(cmd, check=None)` escape hatch:

- `run_text(cmd, ...) -> str` — give me stdout; a non-zero exit is a failure (raises `ProcError`).
- `run_ok(cmd, ...) -> CompletedProcess` — never raises on a non-zero exit; I inspect `rc/stdout/stderr`.
- `run_checked(cmd, ...) -> str` — give me stdout; a non-zero exit raises `ProcError` naming the
  command and its stderr (check-style, the shape the old checking wrappers hand-rolled).

`OSError`/`TimeoutExpired` are NEVER swallowed by any policy — they propagate, because a probe whose
command cannot even run is a louder failure than the caller acting on a value.

The drift gate in `make ci-unit` confines `subprocess.run`/`check_output`/`Popen` in `scripts/` to this
module (or to a line carrying `# proc-allow: <reason>`); see `scripts/check_proc_gate.py`.
"""
from __future__ import annotations

import subprocess
from typing import Any, Sequence


class ProcError(RuntimeError):
    """A command exited non-zero (raised by the checked / text policies).

    Carries the returncode and both streams so a caller that must act on the failure does not have to
    re-run the command. `str(exc)` renders the command, the exit code and, when present, the stderr —
    the same shape the old per-module checking wrappers produced by hand.
    """

    def __init__(self, cmd: Sequence[str], returncode: int,
                 stdout: str = "", stderr: str = "") -> None:
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        shown = " ".join(str(c) for c in cmd)
        detail = (stderr or stdout).strip() or "no output"
        super().__init__(f"{shown!r} exited {returncode}: {detail}")


def _cmd(cmd: Sequence[str], *, timeout: float | None, cwd: str | None,
         env: dict[str, str] | None) -> subprocess.CompletedProcess[str]:
    """Run `cmd` capturing both streams, propagating OSError/TimeoutExpired (never swallowed)."""
    return subprocess.run(list(cmd), capture_output=True, text=True,
                          timeout=timeout, cwd=cwd, env=env)


def run_ok(cmd: Sequence[str], *, timeout: float | None = None,
           cwd: str | None = None, env: dict[str, str] | None = None,
           **_: Any) -> subprocess.CompletedProcess[str]:
    """Run `cmd`; return the CompletedProcess. Never raises on a non-zero exit — the caller inspects.

    This is the policy for "failure is a branch I handle here": return rc/stdout/stderr and let the
    caller decide what a non-zero code means. `OSError`/`TimeoutExpired` still propagate (a command
    that cannot be run is not a return-code the caller can inspect).
    """
    return _cmd(cmd, timeout=timeout, cwd=cwd, env=env)


def run_text(cmd: Sequence[str], *, timeout: float | None = None,
             cwd: str | None = None, env: dict[str, str] | None = None,
             **_: Any) -> str:
    """Run `cmd`; return its stdout. A non-zero exit raises `ProcError` (the command's failure is loud).

    This is the policy for "I want the text, and a failed command is a defect": version probes, decoded
    JSON, `gh api` output — sites that previously returned `""` for a failure and let the caller read
    it as "nothing printed".
    """
    r = _cmd(cmd, timeout=timeout, cwd=cwd, env=env)
    if r.returncode != 0:
        raise ProcError(cmd, r.returncode, r.stdout, r.stderr)
    return r.stdout


def run_checked(cmd: Sequence[str], *, timeout: float | None = None,
                cwd: str | None = None, env: dict[str, str] | None = None,
                **_: Any) -> str:
    """Run `cmd`; return its stdout. A non-zero exit raises `ProcError` naming the command + stderr.

    Check-style, the shape the old checking wrappers hand-rolled: the message names the command and its
    stderr so the failure is legible at the raise site. Prefer this over `run_text` when a caller wants
    the loud failure to carry the command and its stderr verbatim.
    """
    r = _cmd(cmd, timeout=timeout, cwd=cwd, env=env)
    if r.returncode != 0:
        raise ProcError(cmd, r.returncode, r.stdout, r.stderr)
    return r.stdout
