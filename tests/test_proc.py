"""Unit tests for scripts/proc.py — the ONE subprocess policy seam (issue #797).

The seam exposes exactly three named policies and no policy default: `run_text` (stdout, raises on
non-zero), `run_ok` (returns rc/stdout/stderr, never raises), `run_checked` (raises naming the command
and its stderr). `run_ok` returns the CompletedProcess so the caller inspects the exit code; the other
two raise on a non-zero exit. `OSError`/`TimeoutExpired` are never swallowed.
"""
from __future__ import annotations

import subprocess
import sys

import pytest

import scripts.proc as proc


def _py_exit(rc: int, out: str = "", err: str = "") -> list[str]:
    return [sys.executable, "-c", f"import sys; sys.stdout.write({out!r}); "
            f"sys.stderr.write({err!r}); sys.exit({rc})"]


# ---------------------------------------------------------------------------
# run_ok — never raises on a non-zero exit; caller inspects rc/stdout/stderr
# ---------------------------------------------------------------------------
def test_run_ok_returns_completed_process_never_raising():
    # Given a command that succeeds
    ok = proc.run_ok(_py_exit(0, "hello"))
    # Then run_ok returns its stdout with rc 0, never raising
    assert ok.returncode == 0
    assert ok.stdout == "hello"

    # Given a command that exits 3
    bad = proc.run_ok(_py_exit(3, "", "boom"))
    # When run_ok is called
    # Then it does NOT raise, and the caller can inspect the rc and stderr
    assert bad.returncode == 3
    assert "boom" in bad.stderr


def test_run_ok_never_swallows_a_timeout():
    # Given a command that sleeps past its timeout
    # When run_ok is called with a tight timeout
    # Then the TimeoutExpired still propagates (a runnable-but-slow command is a real failure)
    with pytest.raises(subprocess.TimeoutExpired):
        proc.run_ok([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.2)


# ---------------------------------------------------------------------------
# run_text / run_checked — stdout, raise on non-zero
# ---------------------------------------------------------------------------
def test_run_text_returns_stdout_on_success():
    assert proc.run_text(_py_exit(0, "ok-out")) == "ok-out"


def test_run_text_raises_on_non_zero():
    with pytest.raises(proc.ProcError) as ei:
        proc.run_text(_py_exit(2, "", "kaboom"))
    assert ei.value.returncode == 2


def test_run_checked_raises_naming_the_command_and_its_stderr():
    cmd = _py_exit(1, "", "the stderr detail")
    with pytest.raises(proc.ProcError) as ei:
        proc.run_checked(cmd)
    msg = str(ei.value)
    # The command is named...
    assert "".join(cmd[2:]) in msg or "python" in msg
    # ...and its stderr is named, so the failure is legible at the raise site.
    assert "the stderr detail" in msg
    assert ei.value.returncode == 1


def test_run_text_loud_failure_never_returns_empty_string():
    """A probe whose command exits non-zero is a raised failure, never a silent ''.

    This is the exact regression the swallowing wrappers (`detect_server._run`, `engine_skills._run`)
    had: they returned '' for a failed command, so version detection read "no version". The seam's
    text policy makes that loud — a command exiting 1 on the binary path raises instead of returning ''.
    """
    failing = _py_exit(1, "", "")
    with pytest.raises(proc.ProcError):
        proc.run_text(failing)
    # The other two policies agree nothing silent is produced.
    with pytest.raises(proc.ProcError):
        proc.run_checked(failing)


# ---------------------------------------------------------------------------
# the seam is the ONLY place subprocess is called from scripts/proc.py
# ---------------------------------------------------------------------------
def test_proc_raises_only_for_non_zero__exit_0_is_clean():
    assert proc.run_text(_py_exit(0)) == ""
    assert proc.run_checked(_py_exit(0)).__class__ is str
