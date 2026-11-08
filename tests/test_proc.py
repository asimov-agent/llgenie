"""Unit tests for scripts/proc.py — the ONE subprocess policy seam (issue #797).

The seam exposes exactly four named policies and no policy default: `run_text` (stdout, raises on
non-zero), `run_ok` (returns rc/stdout/stderr, never raises), `run_checked` (raises naming the command
and its stderr), `run_live` (streams both streams through as the child writes them, same non-raising
`rc` contract as `run_ok`). `run_ok` returns the CompletedProcess so the caller inspects the exit code;
the other two raise on a non-zero exit. `OSError`/`TimeoutExpired` are never swallowed.
"""
from __future__ import annotations

import os
import select
import subprocess
import sys
import threading

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
# run_live — the child's streams reach the caller AS THEY ARE WRITTEN (issue #2089)
# ---------------------------------------------------------------------------
def test_run_live_streams_both_child_streams_through(capfd):
    """`run_live` passes BOTH streams straight through — the caller's log gets the child's bytes.

    `capfd` captures at FILE-DESCRIPTOR level, which is exactly the channel `run_live` uses
    (`stdout=None`/`stderr=None`: the child inherits fd 1/2). A policy that captured
    (`capture_output=True`) would leave those descriptors untouched and this assertion empty —
    that difference is the regression a cold build shows as a 30-60 minute silent log.
    """
    r = proc.run_live(_py_exit(0, "compiling arch 1 of 4\n", "warning: cold cache\n"))
    out, err = capfd.readouterr()
    assert r.returncode == 0
    assert "compiling arch 1 of 4" in out
    assert "warning: cold cache" in err


def test_run_live_returns_the_child_exit_code_and_never_raises():
    """The `rc` contract is `run_ok`'s: a non-zero exit is returned for the caller to inspect."""
    r = proc.run_live(_py_exit(7, "", ""))
    assert r.returncode == 7
    # Nothing is captured, so nothing is re-surfaced — the streams were already streamed.
    assert r.stdout is None and r.stderr is None


def test_run_live_a_line_reaches_the_caller_before_the_child_exits():
    """The progress line is readable WHILE the child is still running — the whole point (issue #2089).

    The child prints one line and then sleeps; the assertion reads the line from a pipe during that
    sleep and requires the runner thread to still be alive, so a capturing implementation (whose bytes
    only appear after the child returns) cannot pass.
    """
    read_fd, write_fd = os.pipe()
    saved_out, saved_err = os.dup(1), os.dup(2)
    os.dup2(write_fd, 1)
    os.dup2(write_fd, 2)
    os.close(write_fd)
    seen: dict[str, subprocess.CompletedProcess] = {}

    def _run() -> None:
        seen["proc"] = proc.run_live(
            [sys.executable, "-u", "-c",
             "import time; print('step 1 of 3: hipcc', flush=True); time.sleep(2)"])

    worker = threading.Thread(target=_run)
    try:
        worker.start()
        ready, _, _ = select.select([read_fd], [], [], 1.5)
        assert ready, "no line reached the caller while the child was still compiling"
        line = os.read(read_fd, 4096).decode()
        assert "step 1 of 3: hipcc" in line
        assert worker.is_alive(), "the line only arrived after the child exited (captured, not streamed)"
    finally:
        worker.join()
        os.dup2(saved_out, 1)
        os.dup2(saved_err, 2)
        os.close(saved_out)
        os.close(saved_err)
        os.close(read_fd)
    assert seen["proc"].returncode == 0


# ---------------------------------------------------------------------------
# the seam is the ONLY place subprocess is called from scripts/proc.py
# ---------------------------------------------------------------------------
def test_proc_raises_only_for_non_zero__exit_0_is_clean():
    assert proc.run_text(_py_exit(0)) == ""
    assert proc.run_checked(_py_exit(0)).__class__ is str
