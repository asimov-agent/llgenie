#!/usr/bin/env python3
"""The #902 restore condition, as a measurement (issue #817's runner starvation recovery).

When the bot fleet was paused 2026-10-28 (#902, recorded in `bots/pause.toml`), the reason was a
saturated runner queue: jobs sat `queued` because no runner picked them up. So the restore condition
is the inverse, measured against the live queue, exactly as `bots/pause.toml` declares:

    restore.N_readings               consecutive healthy readings required
    restore.K_minutes_apart          minutes that must pass between readings
    restore.in_progress_within_minutes   a queued `pull_request` CI run must reach `in_progress`
                                         within this many minutes of creation

A QUEUE IS HEALTHY when every queued `pull_request` CI run reaches `in_progress` within
`in_progress_within_minutes` of creation. One reading samples the live `/actions/runs` list once;
`restore` is true only when N consecutive readings, K minutes apart, are all healthy.

Once the queue is healthy, the workflows to re-enable come from the same record, in order:
`restore_first` first (cheap common bots so the board wakes early), then `restore_after` (the
heaviest last, so they do not re-saturate a just-drained queue). `gh workflow enable <file>` is the
restore action; this script prints the ordered list, it never touches the API.

Commands:
    bots_restore_health.py restore   # print the ordered restore list (derived from bots/pause.toml)
    bots_restore_health.py measure --repo owner/repo [--gh PATH] [--now ISO-8601]
                                   # sample the live queue once; exit 0 if healthy, 1 if not

`--gh` lets a test drive a stub binary, exactly as all_pipelines' `ALL_PIPELINES_GH` and ci_requeue's
`CI_REQUEUE_GH`. `--now` lets a test fix the clock.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_pause() -> dict:
    """`bots/pause.toml` parsed — the single source of truth for the pause and its restore."""
    return tomllib.loads((REPO_ROOT / "bots" / "pause.toml").read_text())


def _gh(exe: str | None) -> str:
    return os.environ.get("BOTS_RESTORE_HEALTH_GH") or exe or "gh"


def run_gh(args: list[str], gh: str) -> str:
    r = subprocess.run([gh, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"[bots_restore_health] `gh {' '.join(args)}` failed:\n{r.stderr.strip()}")
    return r.stdout or ""


def sample_queue(repo: str, gh: str, in_progress_within_minutes: int,
                 now: str | None = None) -> tuple[bool, list[str]]:
    """One reading: is every queued `pull_request` CI run reaching `in_progress` on time?

    Returns `(healthy, problems)` — problems names each stuck run (workflow + id + age) so the
    report says what is still wrong, not just that the queue is wrong.
    `now` ISO-8601 (test/CLI override) is the observation time; a run's age is
    `now - run.created_at`. A run that reached `in_progress` before `now` (status != "queued") is not
    a problem: the queue picked it up.
    """
    t0 = datetime.fromisoformat(now) if now else datetime.now(timezone.utc)
    raw = run_gh(["api", f"repos/{repo}/actions/runs", "--paginate",
                  "--jq", ".workflow_runs[] | select(.event == \"pull_request\") | "
                         "{workflow: .name, id: (.id|tostring), status, created_at}"], gh)
    problems: list[str] = []
    for doc in _load_json(raw):
        if doc.get("status") == "queued":
            created = datetime.fromisoformat((doc.get("created_at") or "").replace("Z", "+00:00"))
            age_min = (t0 - created).total_seconds() / 60.0
            if age_min > in_progress_within_minutes:
                problems.append(f"{doc['workflow']} (run {doc['id']}, queued {age_min:.0f} min)")
    return (len(problems) == 0, problems)


def _load_json(text: str) -> list[dict]:
    out: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def restore_order() -> list[str]:
    """`restore_first` + `restore_after` in order — the workflows to `gh workflow enable`."""
    cfg = load_pause()
    return list(cfg.get("restore_first", [])) + list(cfg.get("restore_after", []))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("restore", help="print the ordered restore list")
    m = sub.add_parser("measure", help="sample the live queue once; 0 = healthy, 1 = stuck")
    m.add_argument("--repo", required=True, help="owner/repo")
    m.add_argument("--gh", default=None, help="path to gh (default: BOTS_RESTORE_HEALTH_GH / gh on PATH)")
    m.add_argument("--now", default=None, help="ISO-8601 observation time (test/CLI override)")
    m.add_argument("--readings", type=int, default=None,
                   help="N healthy readings required (default: bots/pause.toml restore.N_readings)")
    m.add_argument("--apart", type=int, default=None,
                   help="minutes between readings (default: restore.K_minutes_apart)")
    a = ap.parse_args(argv)
    if a.cmd == "restore":
        for w in restore_order():
            print(w)
        return 0
    cfg = load_pause()["restore"]
    n = a.readings or int(cfg["N_readings"])
    apart = a.apart or int(cfg["K_minutes_apart"])
    within = int(cfg["in_progress_within_minutes"])
    # N consecutive readings, K minutes apart, each healthy. A single `measure` call is ONE reading;
    # the caller (workflow/cron) is what spaces them K minutes apart. We apply `within` and report.
    healthy, problems = sample_queue(a.repo, _gh(a.gh), within, a.now)
    if healthy:
        print(f"queue healthy: no queued pull_request run is stuck > {within} min")
    else:
        print(f"queue NOT healthy ({len(problems)} stuck > {within} min):")
        for p in problems:
            print(f"  {p}")
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
