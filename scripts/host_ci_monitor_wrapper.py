#!/usr/bin/env python3
"""Hermes monitor-script wrapper for `make ci-monitor` (issue #3013; hardened by issue #3016).

Runs the llgenie repo's incident snapshot (`scripts/ci_monitor.py` via the Makefile target) and
passes its stdout through unchanged. The Makefile is the canonical implementation; this wrapper only
guarantees the monitor gate's requirement — byte-stable stdout per state class: every broken state
prints one stable `MONITOR-ERROR` line so the gate sees a stable state instead of a flapping prompt.

It reads from a dedicated monitor clone (never the user's checkout): the clone is ff-refreshed to
origin/main when clean, so the wrapper tracks the target as it lands on main.

Issue #3016 hardened two blind spots measured on the host:

- The refresh used to ignore the exit status of `git fetch` / `git merge --ff-only` and returned
  silently on a dirty tree. Every broken refresh then fell through to `make` on a stale tree and
  printed `MONITOR-ERROR make-ci-monitor-failed` — the exact line the tick contract reads as "the
  target has not landed yet: do nothing". The clone sat on `786239627c1a` for ~12h while main
  already carried the target. A failed refresh (or a dirty clone) now prints its own stable line
  `MONITOR-ERROR clone-refresh-failed`, so "I could not refresh" can never masquerade as "nothing to
  do".
- When make exited 0 the wrapper wrote only `proc.stdout`, so `scripts/ci_monitor.py`'s
  `MONITOR-ERROR gh-fetch-failed` detail (a stderr line by spec) never reached the cron's stderr.
  make's stderr is now passed through in every outcome.
"""
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(
    os.environ.get(
        "LLGENIE_MONITOR_CLONE", str(Path.home() / ".hermes" / "checkouts" / "llgenie-main")
    )
)
UPSTREAM = os.environ.get("LLGENIE_MONITOR_UPSTREAM", "https://github.com/asimov-agent/llgenie.git")


def _git(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, timeout=timeout)


def _refresh_detail(refresh: subprocess.CompletedProcess) -> str:
    return (refresh.stderr or refresh.stdout or "").strip() or f"git exit {refresh.returncode}"


def _ensure_clone() -> tuple[bool, str]:
    """(ok, detail). ok=False means the clone could not be trusted to carry current main."""
    if not (REPO / ".git").is_dir():
        REPO.parent.mkdir(parents=True, exist_ok=True)
        clone = _git("clone", UPSTREAM, str(REPO), timeout=600)
        if clone.returncode != 0:
            return False, f"clone: {_refresh_detail(clone)}"
    dirty = _git("-C", str(REPO), "status", "--porcelain").stdout.strip()
    if dirty:
        return False, f"clone dirty: {dirty.splitlines()[0]}"
    fetch = _git("-C", str(REPO), "fetch", "origin", "main")
    if fetch.returncode != 0:
        return False, f"fetch: {_refresh_detail(fetch)}"
    head = _git("-C", str(REPO), "rev-parse", "HEAD").stdout.strip()
    main = _git("-C", str(REPO), "rev-parse", "origin/main").stdout.strip()
    if head != main and _git("-C", str(REPO), "merge-base", "--is-ancestor", head, main).returncode == 0:
        merge = _git("-C", str(REPO), "merge", "--ff-only", "origin/main")
        if merge.returncode != 0:
            return False, f"merge --ff-only: {_refresh_detail(merge)}"
    return True, ""


def main() -> int:
    try:
        ok, detail = _ensure_clone()
        if not ok:
            # Distinct from make-ci-monitor-failed: this is NOT the "not landed yet" carve-out;
            # the monitor is blind and the tick contract says to treat it as an alarm (issue #3016).
            print(f"MONITOR-ERROR clone-refresh-failed: {detail}", file=sys.stderr)
            print("MONITOR-ERROR clone-refresh-failed")
            return 0
        proc = subprocess.run(
            ["make", "-s", "ci-monitor"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except Exception as exc:
        print(f"MONITOR-ERROR make-ci-monitor-failed: {exc}", file=sys.stderr)
        print("MONITOR-ERROR make-ci-monitor-failed")
        return 0
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        print("MONITOR-ERROR make-ci-monitor-failed")
        return 0
    sys.stdout.write(proc.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
