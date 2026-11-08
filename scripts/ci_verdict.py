#!/usr/bin/env python3
"""A finished CI run's verdict: the jobs that reported, held to the decision that selected them (#1111).

A run that was CANCELLED and a run that ran look almost identical from a check-runs listing, and that
is the defect this file answers. Measured 2026-10-30 on run 41134761297 (`CI`, head `0bd5ac6e`,
conclusion `cancelled`):

    guard success · ci-images cancelled · scanner-images cancelled · linux skipped
    => success=3, failed=0, other=5, pending=0

No `linux / unit` row existed at all — the unit gate never ran — and every reader that quotes a
failure count read that head as clean: `0 failures` is what the summary line said, and it was armed
with no unit verdict. The same class of change at `d92ee6a3` (run 41126873965) had the full set with
`linux / unit failure`, so one head proved the change was wrong and the next head proved nothing.

What was missing is not a conclusion, it is a DECISION: `scripts/ci_scope.py` decides which jobs a
diff selects, `ci.yml`'s `guard` job publishes that decision as the `ci-scope-decision` artifact, and
this tool reads it back against the finished run:

  * a job the decision selected that reported `skipped`, `cancelled`, or not at all -> `no_verdict`
    (red) — a gate that never ran is not a gate that passed;
  * a job the decision did NOT select that is skipped -> `skipped_by_decision` (green) — the
    legitimate skip, now named and counted;
  * NO decision on the run at all -> `verdict=none`, red, because nobody decided and "0 failures" is
    not a verdict.

SUPERSEDED is the one case that is not red: `ci.yml` sets `cancel-in-progress` on a pull request, so
every push cancels the run above it, and a cancelled run that a LATER run of the same workflow on the
same branch already replaced is owed nothing — that head's verdict belongs to the newer run. The
check-run is posted `neutral` there, never `success`, so a superseded head still never reads as a
pass. It is the same test `scripts/ci_requeue.py` uses to decide what to re-run.

Why post a check-run at all: a `workflow_run` run creates NO check-run of its own on the commit
(measured on `0bd5ac6e`: the cancelled CI run's rows are the only ones, `auto-merge`'s own run is
absent), so a verdict that only reds its own workflow would be invisible to every check-run reader.
`--check-run-out` writes the `POST /repos/{owner}/{repo}/check-runs` body; the workflow posts it.

The accounting lives in `scripts/ci_scope.py::verify()` (the module that owns the job table), so the
grammar is one place and the network is another.

Commands (stdlib only, `gh` on PATH — `CI_VERDICT_GH` names the binary a test drives instead):

    ci_verdict.py --repo O/R --run-id <id> [--check-run-out FILE]   a finished run, read from GitHub
    ci_verdict.py --jobs FILE [--decision FILE] [--head-sha SHA]    the same decision, from files

Exit codes:
    0  green, or neutral because a later run of the same workflow owns this head
    1  red: a selected job is missing/skipped/cancelled, a job failed, or the run has no decision
    2  the verdict could not be reached (an API call failed, an unreadable artifact): never a pass
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_scope  # noqa: E402
import verdict_roster  # noqa: E402

TAG = "[ci-verdict]"

#: The artifact `ci.yml`'s `guard` job uploads, and the verdict reads back.
ARTIFACT = "ci-scope-decision"

#: The check-run name a reader looks for. It is not derived from a job name on purpose: it must be the
#: same string on a run whose jobs do not exist, which is exactly when it matters most.
CHECK_NAME = "ci-verdict"

#: The verdict's OWN workflow file — the auto-created per-job check-runs whose rows must never be
#: counted as EXTERNAL unjudged reds (#2221). A `workflow_run` workflow auto-creates one check-run
#: per job on the head it runs on (the default branch), named after the job KEY (#1871); `judge` and
#: `guard` rows therefore sit on a main head, and a prior verdict run's red leaves them `failure`.
#: The existing CHECK_NAME skip only sees the *posted* row (named `ci-verdict`), not these auto job
#: rows — so the own-workflow exclusion is by FILE, the identity `workflow_of` resolves, never by the
#: check name. `verdict_roster.VERDICT_WORKFLOW` is that file, so a rename cannot silently drift.
OWN_WORKFLOW_FILE = Path(verdict_roster.VERDICT_WORKFLOW).name  # "ci-verdict.yml"
#: The merger's workflow FILE. auto-merge cancels its own superseded sweeps repo-wide
#: (`cancel-in-progress: true`, #917), so a `merge=cancelled` row at a busy head means "a newer
#: sweep took over", never "the tree is broken" (#2221). Only `cancelled` is the churn; every other
#: auto-merge blocking conclusion (a real `merge=failure`) stays an unjudged red.
AUTO_MERGE_WORKFLOW_FILE = "auto-merge.yml"

#: The conclusions that make a head NOT clean. `scripts/auto_merge.py` refuses a merge on exactly this
#: set (`failure`, `timed_out`, `startup_failure`, `cancelled` and the `neutral` a superseded verdict
#: posts, #1386/#1250), so a verdict that ignored them would call a head clean that can never merge.
#: `tests/test_ci_verdict.py` asserts the two sets stay equal — the merger's rule is the definition.
BLOCKING_CONCLUSIONS = frozenset({"failure", "timed_out", "startup_failure", "cancelled", "neutral"})

#: The Actions run id inside a check-run's `details_url`
#: (`https://github.com/o/r/actions/runs/<run>/job/<job>`) — how a check-run names the workflow that
#: posted it, which the check-runs payload itself does not say.
RUN_IN_DETAILS = re.compile(r"/actions/runs/(\d+)(?:/|$)")

EXIT_GREEN = 0
EXIT_RED = 1
EXIT_ERROR = 2


def _gh(*args: str) -> str:
    """Run `gh` (the binary `CI_VERDICT_GH` names, so a test can drive a stub — as `ci_requeue` does)."""
    exe = os.environ.get("CI_VERDICT_GH") or "gh"
    result = subprocess.run([exe, *args], capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    if result.returncode != 0:
        raise RuntimeError(f"{exe} {' '.join(args)} failed ({result.returncode}): {result.stderr.strip()}")
    return result.stdout


def _api(path: str) -> dict:
    return json.loads(_gh("api", path) or "{}")


def run_info(repo: str, run_id: str) -> dict:
    """The run itself: conclusion, head sha, branch, workflow — what the verdict has to name."""
    return _api(f"repos/{repo}/actions/runs/{run_id}")


def jobs_of(repo: str, run_id: str) -> list[dict]:
    """Every job row of the run (one page of 100; the fan-out is ten job names, see `ci_scope.JOBS`)."""
    payload = _api(f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100")
    jobs = payload.get("jobs") or []
    if int(payload.get("total_count") or 0) > len(jobs):
        raise RuntimeError(
            f"run {run_id} reports {payload.get('total_count')} job(s) and one page returned {len(jobs)}: "
            f"a truncated listing cannot be a verdict")
    return jobs


def check_runs_of(repo: str, head_sha: str) -> list[dict]:
    """Every check-run on the head, latest only — the rows the verdict must agree are all judged.

    `filter=latest` collapses re-runs so a superseded failed attempt does not shadow the row that
    replaced it. The listing paginates by `page` for a fixed `per_page=100` (GitHub's maximum for this
    endpoint), and a busy head exceeds one page — measured 2026-11-08 on a `push` to `main` at head
    `520db900` (run `42452592982`): 192 check-runs, one page returning 100 was NOT truncation, it was
    page 1 of 2. So, exactly like `branch_runs` (issue #1617), the fetch walks pages until `total_count`
    is satisfied (deduping by id) and the guard refuses only a GENUINE shortfall: when the pages that
    can be read still fall short of the reported `total_count`, or a page ends before `total_count` and
    its next adds nothing. A truncated listing is never a verdict; a well-formed multi-page listing is
    not truncation.
    """
    collected: list[dict] = []
    seen: set[int] = set()
    page = 1
    total: int | None = None
    while True:
        # Page 1 carries NO `&page=` (GitHub treats a bare listing as page 1, and the shape is the
        # one every existing stub and the workflow's older reads matched); only later pages add it.
        suffix = "" if page == 1 else f"&page={page}"
        payload = _api(
            f"repos/{repo}/commits/{head_sha}/check-runs?per_page=100&filter=latest{suffix}")
        rows = payload.get("check_runs") or []
        total = int(payload.get("total_count") or 0)
        fresh = [row for row in rows if row.get("id") not in seen]
        collected.extend(fresh)
        seen.update(row.get("id") for row in rows if row.get("id") is not None)
        if total and len(seen) >= total:
            break
        # An empty page, or a page with only already-seen rows, is the end of the listing — never a
        # verdict by itself. The truncation guard below binds only when the pages read still fall
        # short of `total_count` (exactly `branch_runs`'s #1617 contract).
        if not rows or not fresh:
            break
        page += 1
    if total and len(seen) < total:
        raise RuntimeError(
            f"head {head_sha} reports {total} check-run(s) and the pages returned {len(seen)}: "
            f"a truncated listing cannot be a verdict")
    return collected


def workflow_of(repo: str, check_run: dict, cache: dict | None = None) -> dict:
    """The workflow that posted a check-run, from the Actions run id in its `details_url`.

    `{name, path}` where `path` is the workflow FILE (`.github/workflows/x.yml`) and `name` is the
    workflow's own `name:`, as GitHub recorded them on the run. **`path` is the identity**, not the
    name: GitHub stores a run's `name` TRUNCATED (measured: `engine-build-pr-trigger — a pin-bump PR
    starts the producer and waits on it (issue` — the file's `name:` ends `(issue #1633)`), so matching
    the judged roster on the name silently fails for any workflow whose name is long. The file path is
    exact, and the roster now resolves to files for exactly that comparison.

    The check-runs payload itself names the row and the app, never the workflow, so the link back has
    to be the run the row belongs to. A row with no Actions run in it (another app, or a payload with
    no link) is reported under its app, because an unresolvable red must never be silently dropped.
    """
    url = str(check_run.get("details_url") or "")
    m = RUN_IN_DETAILS.search(url)
    slug = ((check_run.get("app") or {}).get("slug") or "unknown")
    if m is None:
        return {"name": f"<app: {slug}>", "path": ""}
    run_id = m.group(1)
    if cache is not None and run_id in cache:
        return cache[run_id]
    info = _api(f"repos/{repo}/actions/runs/{run_id}") or {}
    found = {"name": str(info.get("name") or f"<run {run_id}>"), "path": str(info.get("path") or "")}
    if cache is not None:
        cache[run_id] = found
    return found


def unjudged_reds(repo: str, head_sha: str, judged_files: set[str],
                  check_runs: list[dict] | None = None) -> list[dict]:
    """The head's blocking check-runs that belong to a workflow the verdict did NOT judge (#2116).

    `ci-verdict` judged exactly ONE workflow (`CI`, file `ci.yml`) while `scripts/auto_merge.py`
    refuses the merge on ANY red check-run at the head. Measured on PR #1982 head `aeac049f`:
    `ci-verdict: success`, `autoMergeRequest` armed, and `engine-build-pr-trigger` `failure` (run
    42440650801) — a head that was green on the one surface every reader trusts and unmergeable in
    fact.

    `judged_files` is the judged roster resolved to workflow FILE names (`verdict_roster.judged_files`),
    because that is the only stable identity a check-run resolves to (see `workflow_of`).

    The verdict's own row (`CHECK_NAME`) is skipped: it is the answer being posted, not a finding.
    Everything else that blocks the merge is returned, so the caller can NAME it and refuse to call
    the head clean.
    """
    rows = check_runs if check_runs is not None else check_runs_of(repo, head_sha)
    cache: dict[str, dict] = {}
    out: list[dict] = []
    for row in rows:
        conclusion = str(row.get("conclusion") or "").strip().lower()
        if conclusion not in BLOCKING_CONCLUSIONS:
            continue
        found = workflow_of(repo, row, cache)
        file_name = Path(found["path"]).name
        # The verdict's OWN workflow rows (#2221): a `workflow_run` workflow auto-creates one
        # check-run per job on the head it runs on (the default branch), named after the job KEY
        # (#1871) — so `judge`/`guard` rows sit on a main head and a prior red leaves them `failure`.
        # Counting them would re-count the verdict into its own red (measured run 42461521651 at
        # 07a7db2a: `verdict=green success=10 failure=0` and STILL `conclusion=failure`). The posted
        # row is skipped by its CHECK_NAME above; these auto job rows are skipped by their FILE.
        if file_name == OWN_WORKFLOW_FILE:
            continue
        name = str(row.get("name") or "")
        if ci_scope.normalise_job_name(name) == CHECK_NAME:
            continue
        if file_name in judged_files:
            continue
        # A CANCELLED auto-merge `merge` row (#2221): auto-merge cancels its own superseded sweeps
        # repo-wide (`cancel-in-progress: true`, #917), so `cancelled` is the merger superseding
        # itself on a busy head — churn, not a defect. A real auto-merge failure/timed_out/neutral
        # STILL qualifies below: only `cancelled` is exempt, so the gate is never weakened.
        if file_name == AUTO_MERGE_WORKFLOW_FILE and conclusion == "cancelled":
            continue
        match = RUN_IN_DETAILS.search(str(row.get("details_url") or ""))
        out.append({
            "name": name,
            "conclusion": conclusion,
            "workflow": found["name"],
            "path": found["path"],
            "run_id": match.group(1) if match is not None else "",
            "details_url": str(row.get("details_url") or ""),
        })
    return out


def judged_roster() -> set[str]:
    """The workflow FILES `ci-verdict.yml` judges, read from the checkout the judge runs on (base)."""
    import verdict_roster  # noqa: PLC0415 - the roster module reads the tree, not the network
    files = verdict_roster.judged_files()
    if not files:
        raise RuntimeError(
            f"no judged workflow roster: {verdict_roster.VERDICT_WORKFLOW} names none, so every red "
            f"check-run on the head would be unjudged — a verdict that judges nothing cannot pass")
    return files


def decision_of(repo: str, run_id: str) -> dict | None:
    """The published decision, or None when the run published none.

    A MISSING artifact is a verdict (`none`), never an error: a cancelled run is precisely a run that
    may never have reached the step that writes it. An artifact that EXISTS but cannot be read is an
    error (exit 2) — a transport failure must not be dressed up as "nobody decided".
    """
    listing = _api(f"repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100")
    names = {str(a.get("name")) for a in listing.get("artifacts") or []}
    if ARTIFACT not in names:
        print(f"{TAG} no `{ARTIFACT}` artifact on run {run_id} — this run published no decision")
        return None
    with tempfile.TemporaryDirectory() as directory:
        _gh("run", "download", str(run_id), "--repo", repo, "-n", ARTIFACT, "-D", directory)
        path = Path(directory) / f"{ARTIFACT}.json"
        if not path.is_file():
            raise RuntimeError(f"artifact `{ARTIFACT}` downloaded from run {run_id} holds no {ARTIFACT}.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != ci_scope.DECISION_SCHEMA:
        raise RuntimeError(
            f"run {run_id}'s decision is schema {payload.get('schema')!r}; this verdict reads "
            f"{ci_scope.DECISION_SCHEMA} — a decision it cannot read is not a verdict")
    return payload


def branch_runs(repo: str, branch: str, per_page: int = 100) -> list[dict]:
    """Every run row on the branch, walking past a single API page (issue #1617).

    GitHub's `/actions/runs` listing paginates by `page` for a fixed `per_page`. A busy branch like
    `main` now exceeds one page (2500+ runs, measured 2026-11-02), so a one-page read of 50 rows
    would make the #1582/#1610 truncation guard raise on every healthy verdict. We walk pages until
    the listing is complete — `total_count` satisfied or a page returns no new rows — and let the
    guard object only to a GENUINE shortfall: when the pages we can read still fall short of the
    reported `total_count`. Deduping by run id keeps a retried/stale page from double-counting.

    The only fetch the guard now refuses is a real truncation: a page that ends before `total_count`
    and whose next page adds nothing (an exhausted listing) still raises the #1582/#1610 error.
    """
    collected: list[dict] = []
    seen: set[int] = set()
    page = 1
    total: int | None = None
    while True:
        listing = _api(
            f"repos/{repo}/actions/runs?branch={branch}&per_page={per_page}&page={page}")
        rows = listing.get("workflow_runs") or []
        total = int(listing.get("total_count") or 0)
        fresh = [row for row in rows if row.get("id") not in seen]
        collected.extend(fresh)
        seen.update(row.get("id") for row in rows if row.get("id") is not None)
        if total and len(seen) >= total:
            break
        if not rows or not fresh:
            break
        page += 1
    if total and len(seen) < total:
        raise RuntimeError(
            f"branch {branch} reports {total} run(s) and the pages returned {len(seen)}: "
            "a truncated listing cannot be a verdict")
    return collected


def superseding_run(repo: str, run: dict) -> dict | None:
    """The later run of the SAME workflow on the SAME branch, or None — `ci_requeue`'s supersede test.

    Judged per (workflow, branch), never per `head_sha`: another workflow on the same commit (`scope`,
    `holds`) is not a newer verdict for THIS one, and `ci.yml`'s `cancel-in-progress` leaves exactly
    that shape behind on every push.

    A re-run is a superseder even when `created_at` is unchanged: GitHub keeps the run id and its
    `created_at` across re-runs, bumping only `run_attempt` (#1250 Finding A). Ordering strictly by
    `created_at` would read a cancelled attempt-1 as this head's final conclusion while a live
    attempt-2 owns it, so the newer attempt wins the same-id case before any later-created run.
    """
    branch = run.get("head_branch")
    workflow_id = run.get("workflow_id")
    created = run.get("created_at")
    if not branch or not created:
        return None
    runs = branch_runs(repo, branch)
    same_workflow = [other for other in runs
                     if other.get("workflow_id") == workflow_id]
    attempts = [other for other in same_workflow
                if other.get("id") == run.get("id")
                and int(other.get("run_attempt") or 1) > int(run.get("run_attempt") or 1)]
    if attempts:
        return sorted(attempts, key=lambda r: int(r.get("run_attempt") or 1))[-1]
    later = [other for other in same_workflow
             if str(other.get("created_at") or "") > str(created)]
    return sorted(later, key=lambda r: str(r.get("created_at")))[-1] if later else None


def merged_pr_run(repo: str, run: dict) -> dict | None:
    """The pull request this run belonged to, if it is already MERGED — a post-merge straggler.

    A `pull_request` run created (or completed) after its PR was merged can never publish a
    legitimate scope decision: the diff's jobs already landed on `main`, `ci.yml`'s `guard` never
    produced a `ci-scope-decision` for a diff that will not re-select these jobs (or wrote none at
    all), and the branch may already be deleted. Redding that run only puts a `verdict` failure on
    the head — measured 2026-11-05, run 41948125618 @ 8bc3be7d, created 01:22:53Z ~24 min after
    #1737 merged (00:58:13Z) on a branch since deleted — and confuses the merge gate for the NEXT
    PR, whose run is judged independently.

    Like SUPERSEDED, the answer is `neutral`, never `success`: a straggler's head must never read as
    a pass, but it must not take the board red either.

    `run.pull_requests` is authoritative when present. An empty list means the branch was deleted
    and GitHub dropped the association (`pull_requests` came back `[]` on the straggler), so resolve
    the PR by `head_branch:head_sha` over `state=all`.
    """
    if run.get("event") != "pull_request":
        return None
    prs = run.get("pull_requests") or []
    if prs:
        number = (prs[0] or {}).get("number")
        if not number:
            return None
        pr = _api(f"repos/{repo}/pulls/{number}")
    else:
        branch = run.get("head_branch") or ""
        sha = run.get("head_sha") or ""
        if not branch or not sha:
            return None
        listing = _api(f"repos/{repo}/pulls?state=all&head={branch}&per_page=100")
        candidates = listing if isinstance(listing, list) else listing.get("pulls") or []
        pr = next((p for p in candidates if (p or {}).get("head", {}).get("sha") == sha), None)
        if pr is None and candidates:
            pr = candidates[0]
    if pr and pr.get("state") == "closed" and pr.get("merged"):
        return pr
    return None


def require_settled(jobs: list[dict]) -> None:
    """Refuse a jobs listing whose rows are not all terminal — a mid-upload snapshot is never a verdict.

    A `workflow_run` `completed` event can fire while the run's OWN records are still settling:
    measured 2026-11-07 on the `#2010`/`#1969` class, the judge read a run whose `linux / unit`
    job was mid-upload — the listing still carried `status: in_progress` for it (no `conclusion`)
    even though the run was reported complete. `ci_scope.verify()` then counted that row as
    `pending`, producing a `no_verdict` for a run that was going to conclude green a moment later.

    A row is terminal only when BOTH it reports `status: completed` AND it carries a non-empty
    `conclusion`. The second half is the `#2046`/`#2035` recurrence: GitHub's jobs API writes a
    finishing row's `status` before its `conclusion`, so a `completed` row with an empty
    conclusion is a run still settling through the conclusion field — counted `pending`, it posts
    a false red exactly like the `in_progress` half (`#2017` closed the status half; this closes
    the conclusion half).

    That is the race this gate closes: a job that has not reported a completed conclusion is a run
    still in flight, and the verdict must not be reached — `raise RuntimeError` so the caller exits
    2 and the `ci-verdict.yml` judge surfaces it as its own unreachable-verdict failure, never as a
    posted `ci-verdict: failure` on a head whose rows were not all there yet.
    """
    unsettled = [j.get("name") for j in jobs
                 if not ((j.get("status") or "").strip().lower() == "completed"
                         and (j.get("conclusion") or "").strip())]
    if unsettled:
        raise RuntimeError(
            f"run is not settled: {len(unsettled)} job(s) have not reported `completed` with a "
            f"conclusion — {', '.join(str(n) for n in unsettled)}; a mid-upload run cannot be judged")


def verdict_lines(result: dict, run: dict | None, superseding: dict | None) -> list[str]:
    """The decision report plus the run it is about — one line per finding, the summary last."""
    header: list[str] = []
    if run:
        # Attribute the verdict to the run it JUDGED, not to the `workflow_run` wrapper's own head
        # (which is always the default branch and makes a PR-run red look like a merge-tip red — #1862).
        attribution = f"event={run.get('event') or '-'}"
        prs = [p.get("number") for p in (run.get("pull_requests") or []) if p.get("number")]
        if prs:
            attribution += f" pr={'+'.join(str(p) for p in prs)}"
        branch = (run.get("head_branch") or "").strip()
        if branch:
            attribution += f" branch={branch}"
        header.append(
            f"{TAG} run {run.get('id')} {run.get('name') or ''} head={str(run.get('head_sha'))[:7]} "
            f"{attribution} conclusion={run.get('conclusion') or run.get('status')}")
    lines = header + result["lines"]
    if superseding is not None:
        lines.append(
            f"{TAG} SUPERSEDED by run {superseding.get('id')} "
            f"({superseding.get('conclusion') or superseding.get('status')}) on "
            f"{superseding.get('head_branch')} — a later run of this workflow owns this head, so the "
            f"conclusion posted below is neutral, never success")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hold a finished CI run to its scope decision (#1111).")
    parser.add_argument("--repo", default=os.environ.get("REPO") or "asimov-agent/llgenie")
    parser.add_argument("--run-id", default=os.environ.get("RUN_ID"),
                        help="the finished run to judge (default: $RUN_ID)")
    parser.add_argument("--jobs", default=os.environ.get("CI_VERDICT_JOBS"),
                        help="read the job rows from this file instead of the API (a test, a replay)")
    parser.add_argument("--decision", default=os.environ.get("CI_VERDICT_DECISION"),
                        help="read the decision from this file instead of the artifact")
    parser.add_argument("--head-sha", default=os.environ.get("HEAD_SHA"),
                        help="the commit the verdict is about (default: the run's head sha)")
    parser.add_argument("--check-run-out", default=os.environ.get("CHECK_RUN_OUT"),
                        help="write the POST /check-runs body to this file")
    parser.add_argument("--checks", default=os.environ.get("CI_VERDICT_CHECKS"),
                        help="read the head's check-runs from this file instead of the API "
                             "(a test, a replay)")
    args = parser.parse_args(argv)

    if not args.run_id and not args.jobs:
        print(f"{TAG} FAILED: give --run-id (a finished run) or --jobs (a file of job rows)", file=sys.stderr)
        return EXIT_ERROR

    try:
        run = run_info(args.repo, args.run_id) if args.run_id else None
        jobs = (json.loads(Path(args.jobs).read_text(encoding="utf-8"))
                if args.jobs else jobs_of(args.repo, args.run_id))
        if isinstance(jobs, dict):
            jobs = jobs.get("jobs") or []
        # Settle gate (#2010 / #1969): a run whose own job rows are still settling (a job
        # `in_progress` mid-upload) is never judged — refuse before the decision artifact is
        # read, so a verdict is not reached from a snapshot the run has not finished writing.
        require_settled(jobs)
        if args.decision:
            decision_obj = json.loads(Path(args.decision).read_text(encoding="utf-8"))
            if decision_obj.get("schema") != ci_scope.DECISION_SCHEMA:
                raise RuntimeError(
                    f"{args.decision} is schema {decision_obj.get('schema')!r}, this verdict reads "
                    f"{ci_scope.DECISION_SCHEMA}")
        elif args.run_id:
            decision_obj = decision_of(args.repo, args.run_id)
        else:
            decision_obj = None
        superseding = superseding_run(args.repo, run) if run else None
        # A post-merge straggler (a run on a branch whose PR is already merged) can never publish a
        # legitimate scope decision. Detect it HERE so an API failure in the query is a reachable-
        # verdict error (exit 2), never a traceback and never a silent default. (#1730-class,
        # measured 41948125618 @ 8bc3be7d.)
        merged_pr = merged_pr_run(args.repo, run) if run else None
        # The head's OTHER check-runs (#2116): the verdict must not call a head clean while a red
        # posted by a workflow it does not judge is sitting on it — `auto_merge.py` refuses that merge
        # whatever the verdict says. Read it whenever there is a live judgment (a run id) or an
        # explicit `--checks` file; a pure `--jobs` replay has no head to read and says so below.
        judged: set[str] = set()
        unjudged: list[dict] = []
        if args.checks or args.run_id:
            head_for_checks = args.head_sha or (run or {}).get("head_sha") or ""
            if not head_for_checks:
                raise RuntimeError(
                    "no head sha: the head's check-runs cannot be read, so a red this verdict did not "
                    "judge cannot be ruled out — an unreadable head is not a clean head")
            rows = None
            if args.checks:
                payload = json.loads(Path(args.checks).read_text(encoding="utf-8"))
                rows = payload.get("check_runs") or [] if isinstance(payload, dict) else payload
            judged = judged_roster()
            unjudged = unjudged_reds(args.repo, head_for_checks, judged, rows)
        else:
            print(f"{TAG} NOTE: no run id and no --checks — the head's unjudged check-runs were NOT "
                  f"read (a replay has no head); any real judgment does read them")
    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        # Never a pass: a verdict that could not be reached is reported as its own failure.
        print(f"{TAG} FAILED: could not reach a verdict — {exc}", file=sys.stderr)
        return EXIT_ERROR

    # The verdict's OWN check-run is attributed back into the run's job list (measured on run
    # 42275871131 @ cf88d285, #1882): `ci-verdict.yml`'s `judge` posts a check-run named
    # `CHECK_NAME` to the head, and GitHub lists that posted check-run as a job of the judged run
    # (`workflow_name: "CI"`). `ci_scope.verify()` then sees a `ci-verdict` job that is not in the
    # 10-job decision table, concludes `failure`, and reds a run whose real jobs are all green —
    # a feedback loop (once red, every re-judge re-counts it). The verdict must not judge itself:
    # drop the row named `CHECK_NAME` from the observed set before verifying.
    jobs = [j for j in jobs if ci_scope.normalise_job_name(j.get("name") or "") != CHECK_NAME]
    result = ci_scope.verify(decision_obj, jobs)
    lines = verdict_lines(result, run, superseding)
    if merged_pr is not None:
        lines.append(
            f"{TAG} MERGED-BRANCH STRAGGLER: run is a `pull_request` run whose PR "
            f"#{merged_pr.get('number')} is already merged (state={merged_pr.get('state')}) — "
            f"there is no legitimate scope decision for it, so the verdict posted below is neutral, "
            f"never success and never red")
    if unjudged:
        lines.append(
            f"{TAG} UNJUDGED RED: this head carries {len(unjudged)} check-run(s) that BLOCK the merge "
            f"(`scripts/auto_merge.py` refuses any red at the head, #1386) and this verdict did NOT "
            f"judge — it judges only {sorted(judged)}. A plain `success` here would be the #2116 "
            f"defect, so the verdict is not clean:")
        for red in unjudged:
            run_label = f" run={red['run_id']}" if red["run_id"] else ""
            lines.append(
                f"{TAG}   check {red['name']!r} conclusion={red['conclusion']} "
                f"workflow={red['workflow']!r}{run_label} {red['details_url']}")
    for line in lines:
        print(line)

    head_sha = args.head_sha or (run or {}).get("head_sha") or ""
    if result["verdict"] == ci_scope.GREEN and not unjudged:
        conclusion, code = "success", EXIT_GREEN
    elif superseding is not None or merged_pr is not None:
        conclusion, code = "neutral", EXIT_GREEN
    else:
        conclusion, code = "failure", EXIT_RED

    if args.check_run_out:
        payload = ci_scope.check_run_payload(
            result["verdict"], head_sha, lines, conclusion=conclusion,
            run_label=f"run {args.run_id}" if args.run_id else "replay")
        payload["name"] = CHECK_NAME
        # The title must say what the POSTED conclusion says, never the judged verdict word (#2221):
        # a green VERDICT beside unjudged reds posts conclusion=failure, and a row titled
        # `ci-verdict: green` with a failure conclusion is exactly how the measured false red read
        # ("ci-verdict: green (run 42460411318)"). Only `success` is titled green.
        title_word = {"success": "green", "neutral": "neutral", "failure": "failure"}.get(
            conclusion, conclusion)
        label = f"run {args.run_id}" if args.run_id else "replay"
        payload["output"]["title"] = (f"ci-verdict: {title_word} ({label})")[:255]
        Path(args.check_run_out).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"{TAG} check-run payload -> {args.check_run_out} (conclusion={conclusion})")

    if code == EXIT_RED:
        print(f"{TAG} FAILED: run {(run or {}).get('id') or '-'} has no verdict — "
              f"see the summary line above, which is what a board must quote instead of a failure count",
              file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
