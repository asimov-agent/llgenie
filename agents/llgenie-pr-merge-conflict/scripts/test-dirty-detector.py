#!/usr/bin/env python3
"""Positive/negative controls for dirty-detector.py — prove it fires and prove it stays quiet.

The detector is the only thing that decides whether the hourly LLGenie DIRTY watch wakes the agent,
so it needs evidence in both directions. It reads `gh`, so each case runs it with a stub `gh` placed
first on PATH — no network, no GitHub state mutated.

Cases:
  A  one CONFLICTING PR                    -> prints the conflicting line        (the wake)
  B  no conflicting PRs                    -> prints `conflicting: none`          (the quiet hour)
  C  gh exits non-zero                     -> prints `detector-error: ...`       (never a false all-clear)
  D  determinism: same stub twice          -> byte-identical                     (so the hash gate works)

Run: python3 scripts/test-dirty-detector.py
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
DETECTOR = HERE / "dirty-detector.py"


def run_with_gh(payload: str | None, exit_code: int = 0) -> str:
    """Run the detector with a stub `gh` on PATH. payload=None leaves the PR list empty."""
    with tempfile.TemporaryDirectory() as tmp:
        bindir = pathlib.Path(tmp)
        stub = bindir / "gh"
        body = ["#!/bin/sh"]
        if exit_code:
            body += ["echo 'gh: boom' >&2", f"exit {exit_code}"]
        else:
            body += [f"cat <<'JSON'", payload or "[]", "JSON"]
        stub.write_text("\n".join(body) + "\n")
        stub.chmod(0o755)
        env = dict(os.environ, PATH=f"{bindir}:{env_path()}")
        out = subprocess.run([sys.executable, str(DETECTOR)], capture_output=True, text=True, env=env)  # proc-allow: test control spawns the stubbed detector it verifies
        assert out.returncode == 0, f"detector must always exit 0, got {out.returncode}: {out.stderr}"
        return out.stdout


def env_path() -> str:
    return os.environ.get("PATH", "/usr/bin:/bin")


CONFLICTING = json.dumps([{
    "number": 789,
    "headRefOid": "f9c60f59b579b748d98267d5b1c5943e4024d718",
    "mergeable": "CONFLICTING",
    "mergeStateStatus": "DIRTY",
}])
CLEAN = json.dumps([
    {"number": 767, "headRefOid": "a" * 40, "mergeable": "MERGEABLE", "mergeStateStatus": "BLOCKED"},
    {"number": 788, "headRefOid": "b" * 40, "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN"},
])

failures: list[str] = []


def check(name: str, ok: bool, detail: str) -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok:
        print(f"      {detail}")
        failures.append(name)


# A — the wake
out_a = run_with_gh(CONFLICTING)
check("A conflicting PR prints the wake line",
      out_a.splitlines()[0] == "conflicting: 789@f9c60f59" and "789 f9c60f59 DIRTY" in out_a,
      repr(out_a))

# B — the quiet hour
out_b = run_with_gh(CLEAN)
check("B no conflict prints exactly 'conflicting: none'",
      out_b == "conflicting: none\n", repr(out_b))

# C — a broken read is never an all-clear
out_c = run_with_gh(None, exit_code=3)
check("C gh failure prints detector-error and never 'conflicting: none'",
      out_c.startswith("detector-error:") and "conflicting: none" not in out_c, repr(out_c))

# D — determinism (the hash gate depends on it)
check("D same input is byte-identical (hash gate can suppress)",
      run_with_gh(CONFLICTING) == out_a and run_with_gh(CLEAN) == out_b,
      "output varied between runs")

print()
if failures:
    print(f"FAILED: {len(failures)} case(s): {', '.join(failures)}")
    raise SystemExit(1)
print("OK: 4/4 — detector wakes on a conflict, stays quiet otherwise, never false-clears, deterministic")
