#!/usr/bin/env python3
"""The host CI monitor snapshot (issue #3013).

`make ci-monitor` asks one question, every monitor tick: *what on this repo needs an agent right
now?* It reads the pipelines through the `gh` CLI — read-only, never a rerun/dispatch (queue-pumping
is forbidden by AGENTS) — and prints the incident snapshot:

- `MAIN-RED run=<id> workflow=<name> conclusion=<c>` — a completed main-branch run that failed,
  was cancelled, or timed out;
- `PR-CHECKS pr=<n> head=<sha9> failed=<k>` — an open non-draft PR with `k` failing check buckets;
- `PR-MERGE pr=<n> head=<sha9> merge=<DIRTY|BEHIND>` — an open PR that cannot auto-merge as-is;
- `PR-REVIEW pr=<n> head=<sha9> decision=CHANGES_REQUESTED` — a reviewer holding the PR;
- `MONITOR-OK` — nothing needs attention;
- `MONITOR-ERROR gh-fetch-failed` — the reads themselves failed (detail on stderr).

The snapshot is byte-stable while the incident set is unchanged: lines are sorted and carry no
timestamps, in-flight/pending states are deliberately NOT incidents (they are expected transitions).
The Hermes monitor cron feeds exactly this stdout to its hash-gate: unchanged output suppresses the
agent, a changed snapshot wakes it with the diff.

All `gh` traffic goes through an injectable `fetch` seam so the unit battery replays recorded
payloads with zero network (the probe-replay precedent).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from proc import run_checked

# Conclusions that are incidents once a run is COMPLETED. In-flight states (queued/in_progress/
# waiting) and neutral outcomes (success, skipped) are deliberately absent: their transitions are
# noise a monitor must not wake an agent for.
MAIN_RED_CONCLUSIONS = ("failure", "cancelled", "timed_out")
# A completed red run is an incident only while it is RECENT. Batched cancels and old failures
# age out of the window so the monitor reports the board as it is, not as it was last week.
MONITOR_MAX_AGE_HOURS = 72
# Merge states that block the auto-merge landing and are actionable (rebase onto latest main).
PR_MERGE_INCIDENTS = ("DIRTY", "BEHIND")
# Review decisions a reviewer left for the agent to answer (AGENTS: PR review comments mandatory).
PR_REVIEW_INCIDENTS = ("CHANGES_REQUESTED",)
MONITOR_OK = "MONITOR-OK"
MONITOR_ERROR = "MONITOR-ERROR gh-fetch-failed"


class Fetch:
    """Default seam: read-only gh calls through the scripts/proc.py policy seam."""

    def __init__(self, repo: str, main_limit: int = 100) -> None:
        self.repo = repo
        self.main_limit = main_limit

    def main_runs(self) -> list[dict[str, Any]]:
        out = run_checked(
            [
                "gh", "run", "list", "--repo", self.repo, "--branch", "main",
                "--limit", str(self.main_limit),
                "--json", "databaseId,workflowName,headBranch,event,status,conclusion,updatedAt",
            ],
            timeout=120,
        )
        return json.loads(out)

    def open_prs(self) -> list[dict[str, Any]]:
        out = run_checked(
            [
                "gh", "pr", "list", "--repo", self.repo, "--state", "open", "--limit", "100",
                "--json", "number,headRefOid,mergeStateStatus,reviewDecision,isDraft",
            ],
            timeout=120,
        )
        return json.loads(out)

    def pr_checks(self, pr_number: int) -> list[dict[str, Any]]:
        out = run_checked(
            ["gh", "pr", "checks", str(pr_number), "--repo", self.repo, "--json", "name,bucket"],
            timeout=120,
        )
        return json.loads(out)


def snapshot_lines(
    main_runs: Sequence[dict[str, Any]],
    open_prs: Sequence[dict[str, Any]],
    checks_by_pr: Mapping[int, Sequence[Mapping[str, Any]]],
    now: datetime | None = None,
    max_age_hours: int | None = None,
) -> list[str]:
    """Pure snapshot: recorded payloads in, deterministic incident lines out.

    `now` + `max_age_hours` age out old red runs; a payload without `updatedAt` (recorded probe
    data) is never age-filtered, so replayed snapshots stay byte-stable.
    """
    lines: list[str] = []
    for run in main_runs:
        if (
            str(run.get("headBranch")) == "main"
            and str(run.get("status")) == "completed"
            and str(run.get("conclusion")) in MAIN_RED_CONCLUSIONS
        ):
            updated = str(run.get("updatedAt") or "")
            if now is not None and max_age_hours is not None and updated:
                try:
                    stamp = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                except ValueError:
                    stamp = None
                if stamp is not None and (now - stamp).total_seconds() > max_age_hours * 3600:
                    continue
            lines.append(
                f"MAIN-RED run={run.get('databaseId')} "
                f"workflow={run.get('workflowName')} conclusion={run.get('conclusion')}"
            )
    for pr in open_prs:
        if pr.get("isDraft"):
            continue
        number = int(pr["number"])
        head = str(pr.get("headRefOid") or "")[:9]
        failed = sum(1 for c in checks_by_pr.get(number, []) if str(c.get("bucket")) == "fail")
        if failed:
            lines.append(f"PR-CHECKS pr={number} head={head} failed={failed}")
        merge_state = str(pr.get("mergeStateStatus") or "")
        if merge_state in PR_MERGE_INCIDENTS:
            lines.append(f"PR-MERGE pr={number} head={head} merge={merge_state}")
        if str(pr.get("reviewDecision") or "") in PR_REVIEW_INCIDENTS:
            lines.append(f"PR-REVIEW pr={number} head={head} decision=CHANGES_REQUESTED")
    return sorted(lines)


def build_snapshot(fetch: Any, max_age_hours: int = MONITOR_MAX_AGE_HOURS) -> str:
    try:
        main_runs = fetch.main_runs()
        open_prs = [pr for pr in fetch.open_prs() if not pr.get("isDraft")]
        checks_by_pr = {int(pr["number"]): fetch.pr_checks(int(pr["number"])) for pr in open_prs}
    except Exception as exc:  # the snapshot stays byte-stable even when the reads fail
        print(f"{MONITOR_ERROR}: {exc}", file=sys.stderr)
        return MONITOR_ERROR
    lines = snapshot_lines(
        main_runs, open_prs, checks_by_pr,
        now=datetime.now(timezone.utc), max_age_hours=max_age_hours,
    )
    return "\n".join(lines) if lines else MONITOR_OK


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print the gh-backed CI incident snapshot (issue #3013).")
    parser.add_argument("--repo", default="asimov-agent/llgenie")
    parser.add_argument("--main-limit", type=int, default=100)
    parser.add_argument(
        "--max-age-hours", type=int, default=MONITOR_MAX_AGE_HOURS,
        help="A completed red main run counts as an incident only while updated within this window.",
    )
    parser.add_argument("--fetch", default=None, help="importable callable() -> Fetch (test seam)")
    args = parser.parse_args(argv)
    if args.fetch:
        import importlib

        module_name, _, func_name = args.fetch.partition(":")
        fetch = getattr(importlib.import_module(module_name), func_name)()
    else:
        fetch = Fetch(repo=args.repo, main_limit=args.main_limit)
    print(build_snapshot(fetch, max_age_hours=args.max_age_hours))
    return 0


if __name__ == "__main__":
    sys.exit(main())
