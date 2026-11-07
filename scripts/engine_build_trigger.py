#!/usr/bin/env python3
"""The "will" arm of the pin-bump gate: a PR that repins an engine triggers the engine-build producer.

The merged gate `scripts/check_engine_pins_published.py` is the "may" arm (issue #1622): a pin-bump PR
cannot MERGE until its exact image tag resolves a registry manifest. But nothing on the PR side ever
STARTS the producer — a bump lands a new pin, the liveness gate reds on the 404, and a human has to
remember to dispatch `engine-build` with `push=true` out-of-band (or a scheduled sweep does it later,
minutes-to-hours of green-wait). Issue #1633 is that missing "will": this script making the PR itself
trigger the producer for exactly the engines it repins, and WAITING on that run's verdict before the
merge window opens.

WHY a new workflow rather than a new ci.yml job: the producer `engine-build.yml` is `workflow_dispatch`-ONLY
with an owner/collaborator-with-write guard that runs BEFORE any secret is read (issue #614). Adding a
`pull_request` trigger to ci.yml would dispatch the producer from every PR; this keeps ci.yml's gate loop
unchanged and gives the trigger its own lifecycle and concurrency. The producer's own guard still runs at
dispatch time — a `push=true` run whose actor is not the owner or a collaborator (or this repo's bot on a
same-repo head, #1571) is still refused by engine-build.yml itself. This script only dispatches; it never
bypasses, weakens or short-circuits that guard. The guard is the producer's and stays where it is.

QUEUE / concurrency: the trigger does not add its own group. A push=true dispatch serialises globally in
engine-build.yml's own `concurrency.group: engine-build-push`, so two bump PRs cannot race on the same
`:<arch>` tag (issue #917); this trigger simply joins that queue and waits its turn. `cancel-in-progress:
false` on the trigger workflow so a stale-head PR does not cancel a producer run that is mid-build (the
same "never cancel a live run" rule as the sweep, #1102 design).

VERDICT, never the dispatch exit code: `gh workflow run` returns 0 whether or not a real run started
(#964's auto-merge trap applies to dispatch too). The fact is the NEW workflow_dispatch-event run's OWN
conclusion — found by diffing the run list before vs after, the exact discipline `scripts/all_pipelines.py`
uses. A run that fails at the producer's guard is reported as refused, not as a bare failure, so a green
board cannot disguise an unverifiable dispatch.

HERMETIC: when the change repins nothing, nothing is dispatched and no API is touched — the same rule as
the may-arm ("no engine this change repins => green and no network"). The repin set comes from
`check_engine_pins_published.repinned_engine_ids` (the params-FILE diff, one shared logic with the merged
gate, not a hand-written roster). Inputs narrow a manual re-dispatch but never widen the committed scope.

Usage:
    python3 scripts/engine_build_trigger.py check [--base REF] [--engine ID] [--arch A] [--dry]
        dispatch engine-build push=true for every engine this change repins (scoped to --engine/--arch if given),
        await each run's verdict, exit 0 only when every dispatched run concluded success. `--dry` prints the
        dispatch plan and exits without dispatching. No repin => green, hermetic, prints nothing dispatched.
    python3 scripts/engine_build_trigger.py report [--base REF] [--engine ID]
        print the repinned engine set and the dispatch plan (never dispatches).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import base_ref  # noqa: E402
import check_engine_pins_published as cpp  # noqa: E402

#: The producer workflow AI a bump triggers. Matched by FILE NAME (the dispatch target), not by name:.
ENGINE_BUILD_WORKFLOW = "engine-build.yml"
# The runs API returns this path with no leading slash. A filter that requires the slash
# matches nothing, so a dispatch that did start is reported as "no run appeared" (PR #1696,
# run 41695838003).
ENGINE_BUILD_PATH = ".github/workflows/engine-build.yml"
DISPATCH_TIMEOUT = 90  # seconds a workflow_dispatch run has to appear
POLL_SECONDS = 20      # between verdict polls
DEFAULT_MAX_WAIT = 240  # minutes a push=true build may take before the trigger gives up
# The producer cell allows 240 minutes and this trigger's job allows 250. A shorter wait
# reddens the PR while the build is still running.
#: A single `gh api` call must never hold a poll loop open past its own deadline
#: (issue: a stalled registry/API call blocks `subprocess.run` with no timeout, so
#: the `time.time() > deadline` bound below is never reached and the trigger hung
#: ~69 min past its 60-min DEFAULT_MAX_WAIT on run 42180155072). This caps each
#: subprocess it performs; a timeout yields an empty response so the loop keeps
#: polling until the deadline and then fails with the existing clear message.
SUBPROCESS_TIMEOUT = 30  # seconds a single shell/gh call may take


def _sh(args: list[str]) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT).stdout  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (timeout so a stalled call cannot hold the poll past its deadline)
    except subprocess.TimeoutExpired:
        return ""  # no verdict this poll; the caller's deadline check decides


def _dispatch_ref(explicit: str) -> str:
    """A branch or tag GitHub will accept as a workflow_dispatch ref.

    `pull_request` checkouts are detached. `git rev-parse --abbrev-ref HEAD` is then the
    literal `HEAD`, and `gh workflow run --ref HEAD` returns HTTP 422 `No ref found for: HEAD`
    (PR #1696). `GITHUB_HEAD_REF` is the source branch Actions sets for that event. A real
    branch name passed in, or a non-detached checkout, still wins.
    """
    name = (explicit or "").strip()
    if name and name != "HEAD":
        return name
    head_ref = os.environ.get("GITHUB_HEAD_REF", "").strip()
    if head_ref and head_ref != "HEAD":
        return head_ref
    symbolic = _sh(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()
    if symbolic and symbolic != "HEAD":
        return symbolic
    print("[will] refusing to dispatch: checkout is detached (git ref is HEAD) and "
          "GITHUB_HEAD_REF is unset. Pass --branch or BRANCH= the PR head branch.",
          file=sys.stderr)
    return ""


def _gh(repo: str, *args: str, gh: str = "gh") -> str:
    return _sh([gh, "api", f"repos/{repo}/actions/runs" + (args[0] if args else ""), *args[1:]])


def repinned(base: str, engine_filter: str = "") -> list[str]:
    """Engine ids this change repins vs `base`, optionally narrowed to one engine."""
    ids = [e for e in cpp.repinned_engine_ids(base) if not engine_filter or e == engine_filter]
    return ids


def _existing_run_ids(repo: str, gh: str) -> set[str]:
    """workflow_dispatch run ids for engine-build currently known (before our dispatch)."""
    raw = _gh(repo, "?per_page=100", gh=gh)
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return set()
    runs = payload.get("workflow_runs", []) if isinstance(payload, dict) else []
    found: set[str] = set()
    for run in runs:
        if run.get("event") != "workflow_dispatch":
            continue
        # The runs API returns this path with no leading slash. `.lstrip("/")` matches the
        # real shape AND tolerates a stray leading slash, so the #2043 jq-filter fix is kept
        # behaviourally while this reads the raw dict it can also diff for discovery (#1696).
        if str(run.get("path") or "").lstrip("/") != ENGINE_BUILD_PATH:
            continue
        found.add(str(run.get("id")))
    return found


def _workflow_run_args(gh: str, repo: str, branch: str, fields: list[str]) -> list[str]:
    """`gh workflow run` argv. Each input is its own `--field`; a second value after one
    `--field` is a positional and is dropped, which dispatched `engine=vllm` with `push` left
    at its default false (PR #1696, run 41695838003 skipped the GHCR login)."""
    cmd = [gh, "workflow", "run", ENGINE_BUILD_WORKFLOW, "--repo", repo, "--ref", branch]
    for field in fields:
        cmd.extend(["--field", field])
    return cmd


def _dispatch_and_wait(repo: str, branch: str, engine: str, arch: str,
                       wait_min: int, gh: str) -> dict:
    """Dispatch engine-build push=true for ONE engine, await the NEW run's own verdict (#964 discipline).

    Returns {run_id, status, conclusion, guard_refused}. `gh workflow run` exit 0 is never a verdict.
    """
    before = _existing_run_ids(repo, gh)
    fields = [f"engine={engine}", "push=true"]
    if arch:
        fields.append(f"arch={arch}")
    # Exit 0 is not a verdict (#964). A non-zero exit means the dispatch itself was rejected
    # (for example HTTP 422), so there is no run to await.
    try:
        dispatched = subprocess.run(_workflow_run_args(gh, repo, branch, fields), check=False,  # proc-allow: engine-build dispatch is a deliberate CLI dispatch on the seam's tracked remainder (#797); check=False is required because gh workflow run exit 0 is not a verdict (the NEW run is awaited below, #964)
                                     capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT)
    except subprocess.TimeoutExpired:
        # The dispatch call itself stalled; the discovery loop below still looks for the
        # NEW workflow_dispatch run (the real verdict) and bails at DISPATCH_TIMEOUT.
        dispatched = None
    if dispatched is not None and dispatched.returncode != 0:
        err = (dispatched.stderr or dispatched.stdout or "").strip()
        return {"run_id": "", "status": "dispatch-failed", "conclusion": "failure",
                "error": err or f"gh workflow run exited {dispatched.returncode}"}
    # The NEW run — a workflow_dispatch-event run not present before — is the fact, not the dispatch exit.
    t0 = time.time()
    wanted = ""
    while not wanted:
        if time.time() - t0 > DISPATCH_TIMEOUT:
            return {"run_id": "", "status": "queued", "conclusion": None,
                    "error": f"no workflow_dispatch run appeared for {ENGINE_BUILD_WORKFLOW} within {DISPATCH_TIMEOUT}s"}
        new = _existing_run_ids(repo, gh) - before
        if new:
            wanted = min(new)  # earliest of the runs that appeared after our dispatch
        else:
            time.sleep(POLL_SECONDS)
    return _await_run(repo, wanted, wait_min, gh)


def _await_run(repo: str, wanted: str, wait_min: int, gh: str) -> dict:
    """Poll one engine-build run until it completes or the wait expires."""
    deadline = time.time() + wait_min * 60
    stall_holder = ""  # an in_progress push run holding the global engine-build-push group, if any
    while True:
        raw = _gh(repo, f"{wanted}", "--jq", "{status, conclusion, completed_at}")
        try:
            run = json.loads(raw)
        except json.JSONDecodeError:
            run = {}
        # A push=true run sits `pending` with 0 jobs and NO heartbeat while it waits behind the
        # global engine-build-push concurrency group (engine-build.yml:80, issue #917/#621). It will
        # never materialise a job until the group holder concludes — a re-dispatch is futile and this
        # trigger must name the holder rather than report a bare "queued/None" (measured stall:
        # #1696 channel 42201352115 behind 42191808660's hung vllm-rocm, 3h+ 0-jobs, issue #1860).
        if run.get("status") in ("pending", "queued") and not stall_holder:
            stall_holder = _push_group_holder(repo, gh)
        # A cancelled/skipped producer is TERMINAL, never something to wait out (issue #1931): a run
        # cancelled mid-wait (concurrency cancel on a newer push) can report `conclusion: "cancelled"`
        # while its `status` never flips to "completed", so concluding on the status field alone polls
        # that corpse forever (measured: trigger run 42326516316 hung in_progress 3.5h on a producer
        # cancelled 12 s after the trigger started, run 42326545643). Stop waiting and name the cause.
        if run.get("conclusion") in ("cancelled", "skipped"):
            return {"run_id": wanted, "status": run.get("status"), "conclusion": run.get("conclusion"),
                    "cause": f"producer {run['conclusion']} — nothing to wait for"}
        # A SUCCESS producer is TERMINAL — nothing left to wait for (issue #1994): a run's
        # `conclusion` is only ever populated once the run has finished, so `conclusion:
        # "success"` is the final verdict even when the `status` field the trigger polled is a
        # stale/mid-flight snapshot that never reports "completed" (measured: trigger run
        # 42352054921 hung 3h54m in_progress on producer 42352074711 `{status: completed,
        # conclusion: success, completed_at: null}`). #1936 made `cancelled`/`skipped` terminal;
        # `success` is the green mirror — without it a succeeded producer holds the trigger past
        # its `wait_min` wall-clock bound instead of concluding promptly with a verdict.
        if run.get("conclusion") == "success":
            return {"run_id": wanted, "status": run.get("status"), "conclusion": "success",
                    "cause": None}
        if run.get("status") == "completed":
            guard = ""
            if run.get("conclusion") == "failure":
                jobs = _gh(repo, f"{wanted}/jobs", "--jq",
                           ".jobs[] | select(.name == \"guard\") | .conclusion")
                guard = "Y" if "failure" in jobs else "N"
            kwargs = {"run_id": wanted, "status": run.get("status"), "conclusion": run.get("conclusion"),
                      "guard_refused": guard == "Y"}
            if stall_holder and not run.get("conclusion"):
                kwargs["stalled_behind"] = stall_holder
            return kwargs
        # Wall-clock bound (issue #1931): a producer that NEVER reports a terminal verdict must not
        # hold the trigger past `wait_min`. On expiry fail with the run id and its last known status —
        # never a bare "concluded queued/None" that reads like a verdict that never happened.
        if time.time() > deadline:
            kwargs = {"run_id": wanted, "status": run.get("status"), "conclusion": run.get("conclusion"),
                      "expired": True}
            if stall_holder and not run.get("conclusion"):
                kwargs["stalled_behind"] = stall_holder
            return kwargs
        time.sleep(POLL_SECONDS)


def _push_group_holder(repo: str, gh: str) -> str:
    """In-progress engine-build push run holding the global `engine-build-push` group (the gate a
    pending push=true dispatch waits behind). Empty when none found — the gate is free then, so a
    pending run is worth surfacing to the producer logic rather than blaming a holder."""
    raw = _gh(repo, "?per_page=100", "--jq",
              '.workflow_runs[] | select(.path == ".github/workflows/engine-build.yml") | '
              'select(.status == "in_progress") | select(.event == "workflow_dispatch") | '
              'select([.display_title] | length > 0) | .id | tostring', gh=gh)
    ids = [line.strip() for line in raw.splitlines() if line.strip()]
    return min(ids) if ids else ""


def _branch_producers(repo: str, branch: str, gh: str) -> list[dict]:
    """workflow_dispatch engine-build runs on `branch`, newest first."""
    raw = _gh(repo, f"?branch={branch}&event=workflow_dispatch&per_page=20", "--jq",
              '[.workflow_runs[] | select(.path == ".github/workflows/engine-build.yml" or '
              '.path == "/.github/workflows/engine-build.yml") | {id: (.id|tostring), status, '
              'conclusion, head_sha}]', gh=gh)
    try:
        rows = json.loads(raw) if raw.strip() else []
    except json.JSONDecodeError:
        return []
    return rows if isinstance(rows, list) else []


def _run_builds_engine(repo: str, run_id: str, engine: str, gh: str) -> bool:
    raw = _gh(repo, f"{run_id}/jobs", "--jq", ".jobs[].name", gh=gh)
    prefix = f"engine-build-{engine}-"
    return any(line.strip().startswith(prefix) for line in raw.splitlines())


def _params_match(sha: str) -> bool:
    """True when `sha` touches the same engine params as HEAD.

    A commit-message rewrite keeps the image identical. Reusing that producer avoids a second
    multi-hour build of the same pins.
    """
    head = _sh(["git", "rev-parse", "HEAD"]).strip()
    if not sha or sha == head:
        return True
    _sh(["git", "fetch", "--no-tags", "origin", sha])
    kind = _sh(["git", "cat-file", "-t", sha]).strip()
    # Compared on its own line: a `"git"` argv and the word commit on one line is read as
    # `git commit` by check-pr-authors (issue #840).
    if kind != "commit":
        return False
    return _sh(["git", "diff", "--stat", sha, "HEAD", "--", "containers/engines/params"]).strip() == ""


def _reusable_producer(repo: str, branch: str, engine: str, gh: str) -> dict:
    """An engine-build already running or green on `branch` for the same params. Empty if none."""
    for run in _branch_producers(repo, branch, gh):
        run_id = str(run.get("id") or "")
        status = str(run.get("status") or "")
        if not run_id or not _run_builds_engine(repo, run_id, engine, gh):
            continue
        if not _params_match(str(run.get("head_sha") or "")):
            continue
        if status in {"queued", "in_progress", "waiting", "pending", "requested"} or run.get("conclusion") == "success":
            return {"run_id": run_id, "status": status, "conclusion": run.get("conclusion")}
    return {}


def check(base: str, engine_filter: str = "", arch: str = "", dry: bool = False, repo: str = "",
          branch: str = "", wait_min: int = DEFAULT_MAX_WAIT, gh: str = "gh") -> int:
    """Dispatch + await a push=true engine-build for every repinned engine; 0 when all succeeded.

    No repin => print and return 0 with no dispatch (hermetic). `dry` prints the plan and never dispatches.
    """
    ids = repinned(base, engine_filter)
    if not ids:
        print("[will] no engine this change repins; nothing to dispatch (hermetic, same rule as the may-arm)")
        return 0
    repo = repo or base_ref.BASE_REPO
    branch = _dispatch_ref(branch)
    if not branch:
        return 1
    print(f"[will] {len(ids)} repinned engine(s) vs {base}: {', '.join(sorted(ids))}")
    if dry:
        for e in sorted(ids):
            print(f"  would dispatch engine-build push=true engine={e}{f' arch={arch}' if arch else ''} @ {branch}")
        print("[will] dry-run: nothing dispatched")
        return 0
    failures = 0
    for e in sorted(ids):
        existing = _reusable_producer(repo, branch, e, gh)
        if existing and existing.get("conclusion") == "success":
            print(f"[will] engine-build already succeeded for engine={e} @ {branch}: "
                  f"run {existing['run_id']}; not dispatching again")
            outcome = existing
        elif existing:
            print(f"[will] engine-build already in progress for engine={e} @ {branch}: "
                  f"run {existing['run_id']}; awaiting it, not dispatching again")
            outcome = _await_run(repo, existing["run_id"], wait_min, gh)
        else:
            print(f"[will] dispatching engine-build push=true engine={e}{f' arch={arch}' if arch else ''} @ {branch}")
            outcome = _dispatch_and_wait(repo, branch, e, arch, wait_min, gh)
        if outcome.get("guard_refused"):
            print(f"[will] FAIL engine={e}: producer refused at its own trigger guard "
                  f"(run {outcome.get('run_id')}) — NOT VERIFIED, not a bare failure", file=sys.stderr)
            failures += 1
        elif outcome.get("cause"):
            print(f"[will] FAIL engine={e}: {outcome['cause']} (run {outcome.get('run_id')})",
                  file=sys.stderr)
            failures += 1
        elif outcome.get("expired"):
            msg = (f"[will] FAIL engine={e}: wait bound ({wait_min} min) expired — producer run "
                   f"{outcome.get('run_id')} never concluded, last status {outcome.get('status')}")
            if outcome.get("stalled_behind"):
                msg += (f" — STALLED behind engine-build-push group holder run "
                        f"{outcome['stalled_behind']} (that holder must conclude or be owner-cancelled; "
                        f"re-dispatch queues behind the same gate, issue #1860)")
            else:
                extra = f" — {outcome['error']}" if outcome.get("error") else ""
                msg += extra
            print(msg, file=sys.stderr)
            failures += 1
        elif outcome.get("conclusion") != "success":
            extra = f" — {outcome['error']}" if outcome.get("error") else ""
            print(f"[will] FAIL engine={e}: run {outcome.get('run_id')} concluded "
                  f"{outcome.get('status')}/{outcome.get('conclusion')}{extra}", file=sys.stderr)
            failures += 1
        else:
            print(f"[will] OK engine={e}: producer run {outcome.get('run_id')} success")
    if failures:
        print(f"[will] {failures} engine-build run(s) did not succeed — the producer must build+push these "
              f"before the bump may merge (issue #1633)", file=sys.stderr)
        return 1
    print(f"[will] every repinned engine's push=true build succeeded")
    return 0


def report(base: str, engine_filter: str = "") -> int:
    ids = repinned(base, engine_filter)
    print(f"[will] {len(ids)} repinned engine(s) vs {base}: {', '.join(sorted(ids)) or '-'}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("check", "report"), nargs="?", default="check")
    ap.add_argument("--base", default="")
    ap.add_argument("--engine", default="", help="narrow the dispatch to ONE engine id")
    ap.add_argument("--arch", default="", help="narrow the dispatch to one arch (cpu|cuda|rocm|vulkan)")
    ap.add_argument("--dry", action="store_true", help="print the dispatch plan without dispatching")
    ap.add_argument("--repo", default="", help="owner/repo to dispatch in (default: base_ref.BASE_REPO)")
    ap.add_argument("--branch", default="", help="ref to dispatch at (default: current HEAD branch)")
    ap.add_argument("--wait-min", type=int, default=DEFAULT_MAX_WAIT, help="max minutes to await the producer")
    ap.add_argument("--gh", default="gh", help="gh binary (tests inject a fake)")
    args = ap.parse_args(argv)
    base = base_ref.resolve_base(explicit=args.base, quiet=True)
    if args.cmd == "report":
        return report(base, args.engine)
    return check(base, args.engine, args.arch, args.dry, args.repo, args.branch, args.wait_min, args.gh)


if __name__ == "__main__":
    sys.exit(main())
