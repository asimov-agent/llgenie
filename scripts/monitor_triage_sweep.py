#!/usr/bin/env python3
"""Re-read every open run-failure-reactor issue against the live MAIN-RED set (issue #3049).

`make monitor-triage-sweep` answers one question for each filing the reactor already made: *is the
failure this issue names still the red that stands on `main`?* The reactor files an issue the moment a
run fails and never revisits it, so a filing whose workflow went green on a later run stays open
forever and keeps waking a fresh agent — the 6 open reactor issues measured on 2026-11-24 named runs
that no monitor snapshot would report as incidents today.

For every OPEN issue carrying the reactor's filing marker (`<!-- run-fixer: … -->`,
`scripts/run_failure_reactor.py`) — the marker IS the filing: the reactor's own dedupe key, and a filing
can carry no lane label (measured 2026-11-24: #3044 is open, carries the marker, has zero labels), so a
label filter would skip an issue this sweep is named to re-read — the sweep reads
the workflow's completed `main` runs and classifies them with `ci_monitor.classify_main_runs` — the
ONE incident rule, the same one `make ci-monitor` prints, so a sweep verdict and a snapshot can never
disagree (issue #3048). It prints one verdict line per filing:

- `SWEEP issue=<n> workflow=<name> run=<id> superseded-by <run>` — a completed main run of the same
  workflow is newer than the filing and the workflow is not red now: the filing is history, and
  `--apply` closes it (claim comment first, then a comment naming the superseder run, then close);
- `SWEEP issue=<n> workflow=<name> run=<id> live newest-red=<run>` — the workflow's newest completed
  main run is itself a red: the issue stays open and `--apply` comments the run id that is red now;
- `SWEEP issue=<n> workflow=<name> run=<id> no-newer-run` — the read holds no completed main run of
  that workflow after the filing: the sweep cannot prove the failure gone, so the issue stays open.

A filing whose subject a live claim already holds is SKIPPED (counted in `skipped-claim`): the claim
protocol outranks a sweep, exactly like every other bot's read (issues #279/#285).

The final line is the tally: `SWEEP-TALLY re-read=<n> superseded=<n> live=<n> no-newer-run=<n>
skipped-claim=<n>`.

Default mode is DRY: every `gh` issue write is printed as the argv it WOULD run and nothing is sent.
`--apply` is the opt-in that writes, and its writes are only issue writes — a claim comment
(`scripts/bot_claims.py`), the superseder/current-red comment, `gh issue close`, and the claim release.
The sweep never touches a pipeline: no `gh run rerun`, no `workflow_dispatch`, no cancel, no merge
(AGENTS: queue-pumping is forbidden). All reads go through an injectable seam so the unit battery
replays recorded payloads with zero network (the `ci_monitor` precedent).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from typing import Any, Callable, Sequence

import bot_claims
import ci_monitor
from proc import run_checked

DESCRIPTION = "Re-read open run-failure-reactor issues against the live MAIN-RED set (issue #3049)."

#: The reactor's filing marker prefix (`run_failure_reactor.MARKER_PREFIX`): a body carrying it is a
#: reactor filing, and it is the sweep's candidate filter (issue #3049).
REACTOR_MARKER = "<!-- run-fixer:"
#: The lane label the reactor puts on a pipeline/gate/bot failure (issue #2076).
PIPELINES_LABEL = "agent:ci-pipelines-maintainer"
#: The bot name this leg stamps its claims with.
BOT = "monitor-triage"
#: The Technical block fields the reactor writes (`issue_body`'s technical section), read back here.
#: The reactor writes them as `- ` bullets, so the leading bullet is optional here.
WORKFLOW_FIELD_RE = re.compile(r"^(?:-\s+)?\*\*workflow:\*\* `(?P<workflow>[^`]*)`\s*$", re.M)
RUN_FIELD_RE = re.compile(r"^(?:-\s+)?\*\*run:\*\* `(?P<run>\d+)`\s*$", re.M)
MAIN_RUN_FIELDS = "databaseId,workflowName,headBranch,event,status,conclusion,updatedAt"
COMMENT_PAGE = 100


class Fetch:
    """Default seam: read-only `gh` calls through the scripts/proc.py policy seam."""

    def __init__(self, repo: str, main_limit: int = 100) -> None:
        self.repo = repo
        self.main_limit = main_limit

    def main_runs(self) -> list[dict[str, Any]]:
        out = run_checked(
            [
                "gh", "run", "list", "--repo", self.repo, "--branch", "main",
                "--limit", str(self.main_limit), "--json", MAIN_RUN_FIELDS,
            ],
            timeout=120,
        )
        return json.loads(out)

    def open_issues(self) -> list[dict[str, Any]]:
        return bot_claims.paginate_open_issues(
            lambda args: run_checked(["gh", *args], timeout=120), self.repo
        )

    def issue_comments(self, number: int) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        page = 1
        while True:
            raw = run_checked(
                ["gh", "api",
                 f"repos/{self.repo}/issues/{number}/comments"
                 f"?per_page={COMMENT_PAGE}&page={page}"],
                timeout=120,
            )
            arr = json.loads(raw or "[]")
            out.extend(arr)
            if len(arr) < COMMENT_PAGE:
                return out
            page += 1


def reactor_filings(issues: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """The open issues that are reactor filings: the filing marker, with their fields parsed.

    The marker is the reactor's dedupe key (issue #2076), so it alone decides candidacy; the lane label
    is recorded (`pipelines_lane`) rather than required, because a filing can be unlabelled (#3044).
    A filing whose body carries no parseable numeric `**run:**` field (the pre-#2072 shape) is kept
    with `run=None`: it is still an open filing, and the sweep reports it as `no-newer-run` instead of
    guessing at which run it named.
    """
    out: list[dict[str, Any]] = []
    for issue in issues:
        body = issue.get("body") or ""
        if REACTOR_MARKER not in body:
            continue
        labels = {str(l.get("name") or "") for l in issue.get("labels") or []}
        wf = WORKFLOW_FIELD_RE.search(body)
        rid = RUN_FIELD_RE.search(body)
        out.append({
            "number": int(issue.get("number") or 0),
            "workflow": (wf.group("workflow") if wf else ""),
            "run": int(rid.group("run")) if rid else None,
            "title": issue.get("title") or "",
            "pipelines_lane": PIPELINES_LABEL in labels,
            # Kept so a live verdict can tell whether the issue already names the current red run.
            "body": body,
        })
    return out


def live_index(main_runs: Sequence[dict[str, Any]]):
    """Return (workflow -> newest completed RED run id, filing run id -> its superseder, workflow ->
    newest completed main run).

    The first two halves come from `ci_monitor.classify_main_runs` with the age window off — the
    sweep asks "what is red NOW", not "what is recent" — and the third is the same per-workflow
    grouping ordered by `ci_monitor._run_order`, so a filing that named a run OUTSIDE the read window
    can still be placed against the workflow's newest completed run (issue #3049).
    """
    incidents, superseded = ci_monitor.classify_main_runs(main_runs)
    newest_red = {str(r.get("workflowName")): int(r.get("databaseId")) for r in incidents}
    superseded_by = {
        int(r.get("databaseId")): int(r["supersededBy"]) for r in superseded if r.get("supersededBy")
    }
    by_workflow: dict[str, list[dict[str, Any]]] = {}
    for run in main_runs:
        if str(run.get("headBranch")) == "main" and str(run.get("status")) == "completed":
            by_workflow.setdefault(str(run.get("workflowName")), []).append(dict(run))
    newest_completed = {wf: sorted(runs, key=ci_monitor._run_order)[-1]
                        for wf, runs in by_workflow.items()}
    return newest_red, superseded_by, newest_completed


def verdict_for(filing: dict[str, Any], newest_red: dict[str, int], superseded_by: dict[int, int],
                newest_completed: dict[str, dict[str, Any]]) -> tuple[str, int | None]:
    """(verdict, the run id the line names) for one filing, per the issue #3049 rules."""
    workflow, run = filing["workflow"], filing["run"]
    if workflow and workflow in newest_red:
        return "live", newest_red[workflow]
    if run is not None and run in superseded_by:
        return "superseded", superseded_by[run]
    newest = newest_completed.get(workflow) if workflow else None
    # GitHub run ids are creation-monotonic, so a newest completed run carrying a larger id than the
    # filing's is a newer completed run of the same workflow, even when the filing itself fell out of
    # the read window.
    if newest is not None and run is not None and int(newest.get("databaseId") or 0) > run:
        return "superseded", int(newest.get("databaseId") or 0)
    return "no-newer-run", None


def supersede_body(filing: dict[str, Any], by_run: int) -> str:
    return (
        f"Re-read by the monitor triage backfill (`make monitor-triage-sweep`, issue #3049).\n\n"
        f"The failure this issue names (`{filing['workflow']}`, run `{filing['run']}`) is no longer "
        f"the red that stands on `main`: the newest completed `main` run of that workflow is "
        f"`{by_run}`, which is not red. A red a newer completed main run replaced is history, not an "
        f"incident (issue #3048), so this filing is closed as superseded. Nothing was rerun, "
        f"re-dispatched, cancelled or merged to reach this verdict (AGENTS: queue-pumping is "
        f"forbidden)."
    )


def live_body(filing: dict[str, Any], current_red: int) -> str:
    return (
        f"Re-read by the monitor triage backfill (`make monitor-triage-sweep`, issue #3049).\n\n"
        f"This filing stays OPEN: the newest completed `main` run of `{filing['workflow']}` is still "
        f"a red — run `{current_red}` is what is red now (the filing named "
        f"`{filing['run']}`). The live incident is recorded here so the next reader starts from the "
        f"current run id instead of the filing's."
    )


def sweep(*, repo: str, fetch, emit: Callable[[list[str]], None], now: dt.datetime | None = None,
          main_limit: int = 100) -> dict[str, Any]:
    """Re-read every open reactor filing; return lines, verdicts, tally, and the argv it wrote/planned.

    `fetch` supplies `main_runs()`, `open_issues()` and `issue_comments(number)`. `emit(argv)` is the
    write seam: dry mode passes a recorder, `--apply` passes the executor.
    """
    main_runs = fetch.main_runs()
    newest_red, superseded_by, newest_completed = live_index(main_runs)
    filings = reactor_filings(fetch.open_issues())

    lines: list[str] = []
    verdicts: list[dict[str, Any]] = []
    planned: list[list[str]] = []
    counts = {"re-read": 0, "superseded": 0, "live": 0, "no-newer-run": 0, "skipped-claim": 0}

    for filing in sorted(filings, key=lambda f: int(f["number"])):
        number = int(filing["number"])
        comments = fetch.issue_comments(number)
        claimed = bot_claims.occupant(comments, BOT, now=now)
        if claimed:
            counts["skipped-claim"] += 1
            lines.append(
                f"SWEEP issue={number} workflow={filing['workflow'] or '?'} "
                f"run={filing['run'] if filing['run'] is not None else '?'} "
                f"skipped-claim occupant={claimed['who']}"
            )
            continue

        verdict, named = verdict_for(filing, newest_red, superseded_by,
                              newest_completed)
        counts["re-read"] += 1
        counts[verdict] += 1
        if verdict == "superseded":
            lines.append(
                f"SWEEP issue={number} workflow={filing['workflow']} "
                f"run={filing['run']} superseded-by {named}"
            )
        elif verdict == "live":
            lines.append(
                f"SWEEP issue={number} workflow={filing['workflow']} "
                f"run={filing['run']} live newest-red={named}"
            )
        else:
            lines.append(
                f"SWEEP issue={number} workflow={filing['workflow'] or '?'} "
                f"run={filing['run'] if filing['run'] is not None else '?'} no-newer-run"
            )
        verdicts.append({**filing, "verdict": verdict, "named": named})

        argv: list[list[str]] = []
        stamp = now or dt.datetime.now(dt.timezone.utc)
        if verdict == "superseded":
            argv.append(["gh", "issue", "comment", str(number), "--repo", repo, "--body",
                         bot_claims.claim_comment(BOT, "clean", stamp)])
            argv.append(["gh", "issue", "comment", str(number), "--repo", repo, "--body",
                         supersede_body(filing, named if named is not None else 0)])
            argv.append(["gh", "issue", "close", str(number), "--repo", repo])
            argv.append(["gh", "issue", "comment", str(number), "--repo", repo, "--body",
                         bot_claims.done_comment(BOT, stamp, f"closed superseded run {filing['run']}")])
        elif verdict == "live":
            # Record the current red run on the live issue (spec: the write half records it), but only
            # when nothing on the issue already names it — the body OR a comment an earlier pass wrote.
            # The sweep is re-runnable, so a second pass over the same live verdict must plan no write
            # (measured: a re-APPLY on 2026-11-24 re-commented #3042/#3046/#2254 before this guard).
            already_named = str(named) in filing["body"] if named is not None else False
            if not already_named and named is not None:
                already_named = any(str(named) in (c.get("body") or "") for c in comments)
            if named is not None and not already_named:
                argv.append(["gh", "issue", "comment", str(number), "--repo", repo, "--body",
                             live_body(filing, named)])
        for cmd in argv:
            planned.append(cmd)
            # The write seam decides what a write means: dry mode passes a recorder (the argv is
            # printed, nothing is sent), `--apply` passes `execute`, which is the only path that
            # reaches a subprocess.
            emit(cmd)

    tally = " ".join(f"{k}={counts[k]}" for k in
                     ("re-read", "superseded", "live", "no-newer-run", "skipped-claim"))
    lines.append(f"SWEEP-TALLY {tally}")
    return {"lines": lines, "verdicts": verdicts, "tally": tally, "planned": planned,
            "counts": counts}


def execute(argv: list[str]) -> None:
    run_checked(argv, timeout=120)


def record_argv(with_applied: list[list[str]]) -> Callable[[list[str]], None]:
    """The dry-run write seam: record the argv, send nothing."""
    def _emit(cmd: list[str]) -> None:
        with_applied.append(list(cmd))
    return _emit


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=DESCRIPTION)
    ap.add_argument("--repo", default="asimov-agent/llgenie")
    ap.add_argument("--main-limit", type=int, default=100,
                    help="how many main runs to read when classifying (the monitor's window)")
    ap.add_argument("--apply", action="store_true",
                    help="actually post the comments / close the superseded issues (default: dry)")
    args = ap.parse_args(argv)

    now = dt.datetime.now(dt.timezone.utc)
    fetch = Fetch(args.repo, main_limit=args.main_limit)
    if not args.apply:
        planned: list[list[str]] = []
        result = sweep(repo=args.repo, fetch=fetch, emit=record_argv(planned), now=now,
                       main_limit=args.main_limit)
    else:
        result = sweep(repo=args.repo, fetch=fetch, emit=execute, now=now,
                       main_limit=args.main_limit)

    for line in result["lines"]:
        print(line)
    if not args.apply:
        for cmd in result["planned"]:
            print("DRY " + " ".join(c if len(c) < 60 else c[:57] + "..." for c in cmd))
        print(f"SWEEP-MODE dry writes-planned={len(result['planned'])}")
    else:
        print(f"SWEEP-MODE applied writes={len(result['planned'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
