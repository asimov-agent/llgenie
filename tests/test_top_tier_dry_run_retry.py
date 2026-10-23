"""The top-tier dry-run retry bound (issue #399), driven with real subprocesses.

`tests/top_tier_dry_run.py::run_dry_run` is the seam the `--dry` acceptance cases
shell out through. These cases run REAL child processes (no mocked `subprocess`,
no mocked transport): one child that fails with the CLI's own exhausted-budget line
and then succeeds, one that keeps failing, and one that fails for a reason that is
not the Hub. The probe is written to `tmp_path` and executed with `sys.executable`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from top_tier_dry_run import (
    TOP_TIER_DRY_RUN_ATTEMPTS,
    is_transient,
    run_dry_run,
)

# The probe is a real child process whose behaviour is decided by a counter file, so
# the retry seam is exercised across a real process boundary and real exit codes.
_PROBE = '''\
import os, pathlib, sys

counter = pathlib.Path(os.environ["PROBE_COUNTER"])
seen = int(counter.read_text()) if counter.exists() else 0
counter.write_text(str(seen + 1))

mode = os.environ.get("PROBE_MODE", "transient-then-ok")
if mode == "transient-then-ok" and seen == 0:
    sys.stderr.write("[ERROR] HF API still failing after 8 attempts for "
                     "https://huggingface.co/api/models/Qwen/Qwen2.5-7B-Instruct-GGUF\\n")
    raise SystemExit(1)
if mode == "always-transient":
    sys.stderr.write("[ERROR] HF API still failing after 8 attempts for "
                     "https://huggingface.co/api/models/Qwen/Qwen2.5-7B-Instruct-GGUF\\n")
    raise SystemExit(1)
if mode == "not-transient":
    sys.stderr.write("ValueError: bad --count argument\\n")
    raise SystemExit(2)
print("[dry] would download top 1")
'''


def _probe(tmp_path: Path) -> tuple[list[str], dict[str, str]]:
    script = tmp_path / "dry_run_probe.py"
    script.write_text(_PROBE)
    env = {"PROBE_COUNTER": str(tmp_path / "counter")}
    return [sys.executable, str(script)], env


def test_transient_failure_is_retried_once_and_the_retry_passes(tmp_path):
    """A transient Hub failure on the first run is retried; the retry's result is returned."""

    # Given a real child that fails once on the Hub's exhausted-budget line and then succeeds
    cmd, env = _probe(tmp_path)
    env["PROBE_MODE"] = "transient-then-ok"

    # When  the seam runs it
    out, attempts = run_dry_run(cmd, env=env)

    # Then  the retry's zero exit is returned, and exactly two runs happened
    assert out.returncode == 0, out.stderr
    assert attempts == 2
    assert (tmp_path / "counter").read_text() == "2"


def test_a_hub_that_stays_unreachable_fails_loudly_at_the_bound(tmp_path):
    """An unreachable Hub spends the whole stated bound and still returns a named failure."""

    # Given a real child that fails on the Hub's exhausted-budget line every time
    cmd, env = _probe(tmp_path)
    env["PROBE_MODE"] = "always-transient"

    # When  the seam runs it
    out, attempts = run_dry_run(cmd, env=env)

    # Then  it stops at the stated bound with the CLI's own named cause and a non-zero exit
    assert attempts == TOP_TIER_DRY_RUN_ATTEMPTS
    assert out.returncode != 0
    assert "HF API still failing after" in out.stderr
    assert (tmp_path / "counter").read_text() == str(TOP_TIER_DRY_RUN_ATTEMPTS)


def test_a_non_transient_failure_is_never_retried(tmp_path):
    """A failure that is not the Hub's transport is returned on the first run."""

    # Given a real child that fails on a bad argument, not on the network
    cmd, env = _probe(tmp_path)
    env["PROBE_MODE"] = "not-transient"

    # When  the seam runs it
    out, attempts = run_dry_run(cmd, env=env)

    # Then  it is not retried — a regression is never retried into a green
    assert attempts == 1
    assert out.returncode != 0
    assert (tmp_path / "counter").read_text() == "1"


@pytest.mark.parametrize("stderr, expected", [
    # the measured issue #399/#549 failure shape: a read-phase socket timeout
    ("Traceback (most recent call last):\nTimeoutError: The read operation timed out\n", True),
    ("urllib.error.URLError: <urlopen error [Errno 8] nodename nor servname provided>", True),
    ("[ERROR] HF API still failing after 8 attempts for https://huggingface.co/api", True),
    ("ValueError: bad --count argument", False),
    ("AssertionError: candidate row must show tier folder", False),
])
def test_transient_classification(stderr, expected):
    """Only a Hub transport failure is retryable; a bug in the dry run is not."""

    # Given  a failed child process with the given stderr
    out = subprocess.CompletedProcess(args=["x"], returncode=1, stdout="", stderr=stderr)

    # When   the seam classifies it
    # Then   the Hub's transport failures are transient and nothing else is
    assert is_transient(out) is expected
