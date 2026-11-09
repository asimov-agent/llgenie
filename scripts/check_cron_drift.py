#!/usr/bin/env python3
"""check_cron_drift.py — live-vs-versioned planner cron prompt drift gate (issue #2359).

HOST-ONLY, the sibling of check_tick_prompt (#2159/#2136): a CI runner has no live
`$HOME/.hermes/profiles/llgenie-planner/cron/jobs.json`, so this check can only run
where that file exists. It reds whenever the PROMPT of a live planner cron job
diverges from its versioned copy, so a recurring rule the fleet claims to follow
cannot silently drift from the reviewed procedure (#2084 class).

Jobs checked (job-id -> versioned file under agents/llgenie-planner/prompts/):
  db0a3e1a3d7c  llgenie-auto-approve-merge (make auto-merge-recheck, #2101 retry)
  71c5192ebdba  llgenie-auto-rebase-resolve (DIRTY/CONFLICTING + BEHIND dispatch)

The orchestrator tick (`cc5d2bd4083a`) is deliberately NOT checked here: it has its
own dedicated gate (check-tick-prompt, #2136) and its own committed file under
agents/llgenie-planner/prompts/. Extending this table is the intended way to admit a
future recurring prompt — one row per live job, never a hand-kept allowlist.

Exit: 0 every checked prompt identical; 1 any prompt differs (names both byte counts
and the file to apply); 2 the live file or a job is missing, or a read failed
(never a silent "no change").
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: job-id -> versioned prompt file, relative to REPO_ROOT. One row per live planner
#: procedural cron; the tick is covered by check_tick_prompt (separate committed file).
CRON_JOBS: tuple[tuple[str, str], ...] = (
    ("db0a3e1a3d7c", "agents/llgenie-planner/prompts/llgenie-auto-approve-merge.md"),
    ("71c5192ebdba", "agents/llgenie-planner/prompts/llgenie-auto-rebase-resolve.md"),
)


def _load_jobs(live_path: Path) -> list[dict]:
    try:
        data = json.loads(live_path.read_text())
    except Exception as e:  # noqa: BLE001 -- report, never crash
        print(f"[check-cron-drift] ERROR reading {live_path}: {e}")
        sys.exit(2)
    jobs = data.get("jobs") if isinstance(data, dict) else data
    return list(jobs or [])


def _find_job(jobs: list[dict], job_id: str) -> dict | None:
    return next((j for j in jobs if isinstance(j, dict) and j.get("id") == job_id), None)


def check_job(jobs: list[dict], job_id: str, versioned: Path) -> bool:
    """Return True when checked-and-identical; print the verdict; exit(2) on missing/read."""
    job = _find_job(jobs, job_id)
    if job is None:
        print(f"[check-cron-drift] job {job_id} not found in the live jobs.json")
        sys.exit(2)

    live_prompt = job.get("prompt", "")
    if not versioned.exists():
        print(f"[check-cron-drift] versioned copy missing: {versioned}")
        sys.exit(2)
    versioned_text = versioned.read_text()

    # The lint gate commits files with a trailing newline; the live JSON value
    # stores the prompt without one. Strip exactly one trailing newline from the
    # versioned read so the two compare on content, not file-vs-json framing.
    versioned_norm = versioned_text[:-1] if versioned_text.endswith("\n") else versioned_text

    if live_prompt == versioned_norm:
        print(f"[check-cron-drift] OK {job_id}: live prompt == versioned ({len(versioned_norm)} b)")
        return True

    print(f"[check-cron-drift] DRIFT {job_id}: LIVE prompt ({len(live_prompt)} b) != versioned copy "
          f"{versioned.name} ({len(versioned_text)} b)")
    print("  the running job diverged from the reviewed procedure -- apply the versioned file")
    print("  to the live jobs.json (planner's act) or the review has not landed")
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", default=Path.home() / ".hermes/profiles/llgenie-planner/cron/jobs.json")
    ap.add_argument("--root", type=Path, default=REPO_ROOT, help="repo root (versioned files resolve here)")
    args = ap.parse_args()

    live_path = Path(args.live)
    if not live_path.exists():
        print(f"[check-cron-drift] no live {live_path} -- host-only check, nothing to compare")
        return 0

    jobs = _load_jobs(live_path)
    ok = True
    for job_id, rel in CRON_JOBS:
        ok &= check_job(jobs, job_id, args.root / rel)

    print(f"[check-cron-drift] {len(CRON_JOBS)} job(s) checked"
          f"{'' if ok else ' -- drift, apply the versioned prompts'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
