#!/usr/bin/env python3
"""check_tick_prompt.py — the live-vs-versioned tick prompt drift gate (issue #2159).

HOST-ONLY, mirroring profile-drift-alarm: a CI runner has no live
`~/.hermes/profiles/llgenie-planner/cron/jobs.json`, so this check can only run
where that file exists. It reds when the prompt of the live orchestrator cron job
(`cc5d2bd4083a`) diverges from the versioned copy
`agents/llgenie-planner/cron/llgenie-orchestrator-tick.md`.

Exit: 0 prompt identical; 1 prompt differs (names both byte counts); 2 the live
file or job is missing, or a read failed (never a silent "no change").
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LIVE_JOB_ID = "cc5d2bd4083a"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", default=Path.home() / ".hermes/profiles/llgenie-planner/cron/jobs.json")
    ap.add_argument("--versioned", type=Path,
                    default=Path(__file__).resolve().parent.parent
                    / "agents" / "llgenie-planner" / "cron" / "llgenie-orchestrator-tick.md")
    ap.add_argument("--job-id", default=LIVE_JOB_ID)
    args = ap.parse_args()

    live_path = Path(args.live)
    if not live_path.exists():
        print(f"[check-tick-prompt] no live {live_path} -- host-only check, nothing to compare")
        return 0

    try:
        data = json.loads(live_path.read_text())
    except Exception as e:  # noqa: BLE001 -- report, never crash
        print(f"[check-tick-prompt] ERROR reading {live_path}: {e}")
        return 2

    jobs = data.get("jobs") if isinstance(data, dict) else data
    job = next((j for j in (jobs or []) if isinstance(j, dict) and j.get("id") == args.job_id), None)
    if job is None:
        print(f"[check-tick-prompt] job {args.job_id} not found in {live_path}")
        return 2

    live_prompt = job.get("prompt", "")
    versioned = args.versioned
    if not versioned.exists():
        print(f"[check-tick-prompt] versioned copy missing: {versioned}")
        return 2
    versioned_text = versioned.read_text()

    # The lint gate commits files with a trailing newline; the live JSON value
    # stores the prompt without one. Strip exactly one trailing newline from the
    # versioned read so the two compare on content, not on file-vs-json framing.
    versioned_norm = versioned_text[:-1] if versioned_text.endswith("\n") else versioned_text

    if live_prompt == versioned_norm:
        print(f"[check-tick-prompt] OK live prompt == versioned ({len(versioned_norm)} b)")
        return 0

    print(f"[check-tick-prompt] LIVE prompt ({len(live_prompt)} b) != versioned copy "
          f"{versioned.name} ({len(versioned_text)} b)")
    print("  the running job diverged from the reviewed procedure -- apply the versioned file")
    print("  to the live jobs.json (planner's act) or the review has not landed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
