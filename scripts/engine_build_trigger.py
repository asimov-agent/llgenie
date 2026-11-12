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
`check_engine_pins_published.repinned_cells` (tag-identity diff at CELL granularity, issue #2590 —
the engine-level view `repinned_engine_ids`, params-FILE diff UNION tag-identity diff, issue
#2559, stays one shared logic with the merged gate, not a hand-written roster). Inputs narrow a
manual re-dispatch but never widen the committed scope.

Usage:
    python3 scripts/engine_build_trigger.py check [--base REF] [--engine ID] [--arch A] [--dry]
        dispatch engine-build push=true for every (engine, arch) CELL this change repins (narrowed to
        --engine/--arch if given), naming each cell's arch explicitly — an arch-less dispatch of a
        DEFAULT_CPU_ONLY engine builds only its cpu cell and silently drops a repinned GPU cell
        (issue #2590, measured on PR #2582). Await each run's verdict, exit 0 only when every
        dispatched run concluded success. `--dry` prints the dispatch plan and exits without
        dispatching. No repin => green, hermetic, prints nothing dispatched.
    python3 scripts/engine_build_trigger.py report [--base REF] [--engine ID] [--arch A]
        print the repinned cell set and the dispatch plan (never dispatches).
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
DISPATCH_TIMEOUT = 90  # seconds a workflow_dispatch run has to appear
POLL_SECONDS = 20      # between verdict polls
DEFAULT_MAX_WAIT = 60  # minutes a push=true build may take before the trigger gives up
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
    """A ref `gh workflow run --ref` will accept, or "" when the checkout cannot name one.

    A `pull_request` checkout is DETACHED, so `git rev-parse --abbrev-ref HEAD` is the literal
    `HEAD` and `--ref HEAD` is rejected with HTTP 422 `No ref found for: HEAD` (issue #2089,
    carried from PR #1696). Actions exports the source branch of that event as `GITHUB_HEAD_REF`,
    which the workflow also forwards as `BRANCH=`; an explicit `--branch`, that variable, or a
    non-detached checkout's own branch each win in that order. When none of them names a ref this
    returns "" — the caller refuses instead of dispatching at a ref GitHub cannot resolve, and the
    reason it prints names the two inputs that would have resolved it.
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
    return ""


def _gh(repo: str, *args: str, gh: str = "gh") -> str:
    return _sh([gh, "api", f"repos/{repo}/actions/runs" + (args[0] if args else ""), *args[1:]])


def _run_verdict(repo: str, run_id: str, gh: str) -> dict:
    """Read ONE producer run's `{status, conclusion, completed_at}` — falling back to the run LIST on a 404.

    A just-dispatched producer run can 404 on the SINGLE-run endpoint (`/actions/runs/<id>`) for a whole
    wait-bound (token scope / propagation race) while that same run carries a live status in the run LIST
    (`/actions/runs`), and may already have SUCCEEDED (issue #2059; measured producer 42428385314
    `success` while the trigger polled `last status 404` for the full 60-min bound). The single-run 404
    body (`{"message":"Not Found","status":"404"}`) parses as a dict that matches NO terminal branch in
    the await loop, so the old code could never conclude on it. The list entry carries the same
    `status`/`conclusion` fields, so re-resolve there instead of treating 404 as "not concluded".
    Returns `{}` when neither endpoint yields a verdict (the loop's deadline still bounds the wait).
    """
    raw = _gh(repo, f"{run_id}", "--jq", "{status, conclusion, completed_at}", gh=gh)
    try:
        run = json.loads(raw)
    except json.JSONDecodeError:
        run = {}
    if isinstance(run, dict) and run.get("status") != "404" and run.get("message") != "Not Found":
        return run
    # The single-run endpoint 404'd. Keep that verdict so a caller's failure message can NAME it
    # (`last status 404`) rather than reporting an indistinguishable `None` (issue #2059).
    not_found = run if isinstance(run, dict) and run.get("status") == "404" else {
        "status": "404", "message": "Not Found"}
    # The run LIST carries the same fields — resolve from there when it can.
    raw = _gh(repo, "?per_page=100", "--jq",
              '.workflow_runs[] | select((.id|tostring) == "%s") | {status, conclusion, completed_at}'
              % run_id, gh=gh)
    try:
        listed = json.loads(raw)
    except json.JSONDecodeError:
        listed = {}
    if isinstance(listed, dict) and listed.get("status"):
        # Recorded decision, not a silent skip (#1796): the single-run endpoint lied about visibility.
        print(f"[will] producer run {run_id}: 404 on the single-run endpoint — resolved from the run "
              f"list as {listed.get('status')}/{listed.get('conclusion')} (issue #2059)", flush=True)
        return listed
    return not_found


def repinned(base: str, engine_filter: str = "", arch_filter: str = "") -> list[tuple[str, str]]:
    """(engine, variant) CELLS this change repins vs `base`, optionally narrowed.

    Cell granularity is the dispatch unit (#2590): a repinned cell must never be silently
    dropped by the producer's arch-less default narrowing (`DEFAULT_CPU_ONLY` engines build
    cpu only when no arch is named, issue #1836) — the #2582 rocm tag stayed unpublished
    exactly because the trigger dispatched `engine=vllm` with no arch.
    """
    return [(engine, variant) for engine, variant in cpp.repinned_cells(base)
            if (not engine_filter or engine == engine_filter)
            and (not arch_filter or variant == arch_filter)]


def _existing_run_ids(repo: str, gh: str) -> set[str]:
    """workflow_dispatch run ids for engine-build currently known (before our dispatch)."""
    raw = _gh(repo, "?per_page=100", "--jq",
              '.workflow_runs[] | select(.event == "workflow_dispatch") | '
              'select(.path == ".github/workflows/engine-build.yml") | .id | tostring', gh=gh)
    return {line.strip() for line in raw.splitlines() if line.strip()}


def _workflow_run_args(gh: str, repo: str, branch: str, fields: list[str]) -> list[str]:
    """`gh workflow run` argv with ONE `--field` per input.

    `gh workflow run`'s `--field/-f` takes a SINGLE value, so `["--field", "engine=x", "push=true"]`
    hands `push=true` to `gh` as a positional argument and the dispatch is rejected without a run
    ever starting — the shape `main` carried, measured as a pull_request trigger run that dispatched
    nothing and reported a bare `run  concluded queued/None` (issue #2089; run 42423190271 job
    128555865778). Every input gets its own `--field`.
    """
    cmd = [gh, "workflow", "run", ENGINE_BUILD_WORKFLOW, "--repo", repo, "--ref", branch]
    for field in fields:
        cmd.extend(["--field", field])
    return cmd


def _dispatch_and_wait(repo: str, branch: str, engine: str, arch: str,
                       wait_min: int, gh: str) -> dict:
    """Dispatch engine-build push=true for ONE (engine, arch) cell, await the NEW run's own verdict (#964 discipline).

    Returns {run_id, status, conclusion, guard_refused}. `gh workflow run` exit 0 is never a verdict.
    """
    before = _existing_run_ids(repo, gh)
    fields = [f"engine={engine}", "push=true"]
    if arch:
        fields.append(f"arch={arch}")
    # Exit 0 is not a verdict (#964), and a NON-zero exit is a dispatch that never started a run.
    # Report the CLI's own rejection text (`HTTP 422: No ref found for: HEAD`, an unknown input, a
    # permission refusal) instead of awaiting a run that does not exist (issue #2089).
    try:
        dispatched = subprocess.run(_workflow_run_args(gh, repo, branch, fields),  # proc-allow: engine-build dispatch is a deliberate CLI dispatch on the seam's tracked remainder (#797); check=False is required because gh workflow run exit 0 is not a verdict (the NEW run is awaited below, #964)
                                    check=False, capture_output=True, text=True,
                                    timeout=SUBPROCESS_TIMEOUT)
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
    # Await THAT run's verdict.
    deadline = time.time() + wait_min * 60
    stall_holder = ""  # an in_progress push run holding the global engine-build-push group, if any
    while True:
        run = _run_verdict(repo, wanted, gh)
        # A 404 on the single-run endpoint is a POLL RACE, not a verdict (issue #2059): the run may
        # already have SUCCEEDED while `/actions/runs/<id>` keeps answering 404. `_run_verdict` re-reads
        # it from the run LIST, and if that still yields nothing this poll simply keeps watching — the
        # wall-clock bound below still bounds the wait, and the failure names `404` so a reader can tell
        # a poll race from a real conclusion.
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
            # A status of "404" at expiry is a POLL-VISIBILITY failure, not a build result (issue #2059):
            # the producer id never resolved on EITHER endpoint for the whole bound. Name it so a reader
            # can tell this apart from a producer that genuinely concluded and is worth re-reading.
            if run.get("status") == "404" or run.get("message") == "Not Found":
                kwargs["unresolved_404"] = True
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



def check(base: str, engine_filter: str = "", arch: str = "", dry: bool = False, repo: str = "",
          branch: str = "", wait_min: int = DEFAULT_MAX_WAIT, gh: str = "gh") -> int:
    """Dispatch + await a push=true engine-build for every repinned CELL; 0 when all succeeded.

    One dispatch per cell with `engine=<id> arch=<variant>` (#2590): the explicit arch means
    the producer builds the cell this change repinned, never a cpu-only substitute chosen by
    the matrix default. No repin => print and return 0 with no dispatch (hermetic). `dry`
    prints the plan and never dispatches.
    """
    cells = repinned(base, engine_filter, arch)
    if not cells:
        print("[will] no cell this change repins; nothing to dispatch (hermetic, same rule as the may-arm)")
        return 0
    repo = repo or base_ref.BASE_REPO
    branch = _dispatch_ref(branch)
    if not branch:
        # Refuse rather than dispatch at a ref GitHub cannot resolve: a detached checkout used to
        # send `--ref HEAD` and the dispatch died with HTTP 422 (issue #2089). Name both inputs that
        # would have resolved it, so the next reader does not have to infer the workflow change.
        print("[will] refusing to dispatch: the checkout names no ref (detached HEAD) and "
              "GITHUB_HEAD_REF is unset. Pass --branch / BRANCH=${{ github.head_ref }}.", file=sys.stderr)
        return 1
    print(f"[will] {len(cells)} repinned cell(s) vs {base}: "
          f"{', '.join(f'{e}/{v}' for e, v in sorted(cells))}")
    if dry:
        for e, v in sorted(cells):
            print(f"  would dispatch engine-build push=true engine={e} arch={v} @ {branch}")
        print("[will] dry-run: nothing dispatched")
        return 0
    failures = 0
    for e, v in sorted(cells):
        print(f"[will] dispatching engine-build push=true engine={e} arch={v} @ {branch}")
        outcome = _dispatch_and_wait(repo, branch, e, v, wait_min, gh)
        if outcome.get("guard_refused"):
            print(f"[will] FAIL engine={e} arch={v}: producer refused at its own trigger guard "
                  f"(run {outcome.get('run_id')}) — NOT VERIFIED, not a bare failure", file=sys.stderr)
            failures += 1
        elif outcome.get("cause"):
            print(f"[will] FAIL engine={e} arch={v}: {outcome['cause']} (run {outcome.get('run_id')})",
                  file=sys.stderr)
            failures += 1
        elif outcome.get("expired"):
            msg = (f"[will] FAIL engine={e} arch={v}: wait bound ({wait_min} min) expired — producer run "
                   f"{outcome.get('run_id')} never concluded, last status {outcome.get('status')}")
            if outcome.get("unresolved_404"):
                msg += (" — the producer id never resolved on the run endpoint (404 for the whole bound): "
                        "a POLL-VISIBILITY race, not a build result; re-run the trigger / re-check the run "
                        "by hand before treating this as a failure (issue #2059)")
            if outcome.get("stalled_behind"):
                msg += (f" — STALLED behind engine-build-push group holder run "
                        f"{outcome['stalled_behind']} (that holder must conclude or be owner-cancelled; "
                        f"re-dispatch queues behind the same gate, issue #1860)")
            print(msg, file=sys.stderr)
            failures += 1
        elif outcome.get("conclusion") != "success":
            # A rejected dispatch carries its own reason (`HTTP 422: No ref found for: HEAD`, an
            # unknown input, a permission refusal) — print it, so the log says which refusal this
            # was instead of a bare `run  concluded queued/None` (issue #2089).
            extra = f" — {outcome['error']}" if outcome.get("error") else ""
            print(f"[will] FAIL engine={e} arch={v}: run {outcome.get('run_id')} concluded "
                  f"{outcome.get('status')}/{outcome.get('conclusion')}{extra}", file=sys.stderr)
            failures += 1
        else:
            print(f"[will] OK engine={e} arch={v}: producer run {outcome.get('run_id')} success")
    if failures:
        print(f"[will] {failures} engine-build run(s) did not succeed — the producer must build+push these "
              f"cells before the bump may merge (issue #1633)", file=sys.stderr)
        return 1
    print("[will] every repinned cell's push=true build succeeded")
    return 0


def report(base: str, engine_filter: str = "", arch: str = "") -> int:
    cells = repinned(base, engine_filter, arch)
    print(f"[will] {len(cells)} repinned cell(s) vs {base}: "
          f"{', '.join(f'{e}/{v}' for e, v in sorted(cells)) or '-'}")
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
        return report(base, args.engine, args.arch)
    return check(base, args.engine, args.arch, args.dry, args.repo, args.branch, args.wait_min, args.gh)


if __name__ == "__main__":
    sys.exit(main())
