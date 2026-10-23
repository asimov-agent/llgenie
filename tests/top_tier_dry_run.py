"""Bounded retry for the top-tier dry-run subprocesses (issue #399).

The `--download-top-tier --dry` acceptance cases shell out to the real CLI, whose
only non-hermetic step is a live Hugging Face read. `_hf_get` already retries a
transport failure INSIDE the process (#549, `TimeoutError` rides the
`HF_GET_MAX_ATTEMPTS` budget), but when that budget is spent the subprocess exits 1
and the PR-blocking `top-tier` job (`.github/workflows/pipeline.yml` ->
`make ci-top-tier`) goes red on one slow moment of Hub latency — run 39381961586
failed and its unchanged re-run passed, with the Hub read as the only variable.

This seam adds the second half of the bound: the whole dry run is retried once
(`TOP_TIER_DRY_RUN_ATTEMPTS`), so the job's conclusion rests on a stated number of
attempts rather than on one read at one minute. Only a TRANSPORT failure is
retryable — an unreachable Hub that stays unreachable still returns its non-zero
exit with the CLI's own named cause (`[ERROR] HF API still failing after N attempts`),
never a skip and never a soft pass (AGENTS.md "NO SKIPPED TESTS"). Any other
failure (a bad argument, a bug in the discovery code) is returned on the first
attempt, so a regression is never retried into a green.
"""
from __future__ import annotations

import subprocess

# Total attempts for one dry run: the first run plus ONE retry. Stated in README.md
# ("Top-tier dry-run retry") and locked by tests/test_top_tier_dry_run_retry.py.
TOP_TIER_DRY_RUN_ATTEMPTS = 2

# A subprocess failure is a Hub TRANSPORT failure when the CLI's own stderr names it.
# `[ERROR] HF API still failing after N attempts` is the exhausted-budget exit from
# `_hf_get`; the remaining names are the transport classes/messages that reach the CLI
# before (or instead of) that line — TimeoutError from a read phase (issue #549),
# URLError from a connect phase, and the transient HTTP statuses the CLI retries.
TRANSIENT_MARKERS = (
    "HF API still failing after",
    "TimeoutError",
    "timed out",
    "URLError",
    "ConnectionError",
    "Connection reset",
    "RemoteDisconnected",
    "SSLError",
    "Temporary failure in name resolution",
    "429",
    "502",
    "503",
    "504",
)


def is_transient(out: subprocess.CompletedProcess) -> bool:
    """True when a failed dry run failed on the Hub's transport, not on the diff."""
    if out.returncode == 0:
        return False
    stderr = out.stderr or ""
    return any(marker in stderr for marker in TRANSIENT_MARKERS)


def run_dry_run(cmd, *, env=None, timeout=None,
                attempts: int = TOP_TIER_DRY_RUN_ATTEMPTS):
    """Run a `--dry` subprocess, retrying a transient Hub failure within `attempts`.

    Returns `(completed_process, attempts_used)`. A zero exit is returned at once.
    A non-transient non-zero exit is returned at once (no retry: a real failure must
    not be retried into a green). A transient failure is retried until `attempts` is
    spent, and the last result is returned so the caller's assertion fails LOUDLY
    with the CLI's named cause in its message.
    """
    last: subprocess.CompletedProcess | None = None
    used = 0
    if attempts < 1:
        raise ValueError(f"attempts must be >= 1, got {attempts}")
    for used in range(1, attempts + 1):
        last = subprocess.run(cmd, capture_output=True, text=True, env=env,
                              timeout=timeout)
        if last.returncode == 0 or not is_transient(last):
            return last, used
    assert last is not None  # attempts >= 1, so at least one run happened
    return last, used
