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

WAIT BUDGET / REPLACEMENT (issue #2892, measured 2026-11-17 against the four open engine-bump PRs:
6 trigger runs -> 5 completed/failure + 1 grinding 3h, 28 producer dispatches for ~15 distinct cells;
run 44143247189's ROCm cell built 61+ min with NOTHING queued ahead, past the old flat 60-min bound).
Three parts, all in this script: (1) PUBLISHED-SKIP — a repinned cell whose exact tag already resolves a
registry manifest (the may-arm's OWN authority: `check_engine_pins_published.exact_tags` +
`engine_image._digest_http`) is never re-dispatched, so a reopen cycle costs a manifest probe instead of
a full matrix re-shuffle at the back of the `engine-build-push` FIFO. (2) PER-ARCH BUDGET —
`WAIT_MIN_BY_ARCH = {"rocm": 150}` over `DEFAULT_MAX_WAIT = 60`: a cell class whose measured build time
does not fit the flat bound gets a bound that fits; `--wait-min` still overrides every class.
(3) REPLACEMENT CAP — a cancelled/skipped producer gets AT MOST ONE replacement dispatch per cell per
trigger run, awaited on the CARRIED budget (`budget * REPLACEMENT_FACTOR` minus what the cancelled
attempt consumed), so a cancellation storm cannot re-queue the same cell unboundedly.

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
import engine_image as ei  # noqa: E402 - the published-skip probe reuses the may-arm's manifest authority (#2892)

#: The producer workflow AI a bump triggers. Matched by FILE NAME (the dispatch target), not by name:.
ENGINE_BUILD_WORKFLOW = "engine-build.yml"
DISPATCH_TIMEOUT = 90  # seconds a workflow_dispatch run has to appear
POLL_SECONDS = 20      # between verdict polls
DEFAULT_MAX_WAIT = 60  # minutes a non-rocm push=true build may take before the trigger gives up
#: Per-arch wait bounds measured from real producer build times (issue #2892): a cold ROCm cell was
#: still building past 61 min with NOTHING queued ahead (run 44143247189: job start 18:24:26Z, still
#: in_progress at 19:25Z), so the flat 60-min bound guaranteed a red trigger + reopen re-dispatch on
#: every PR repinning a rocm cell. 150 covers the measured cold build plus queue headroom.
WAIT_MIN_BY_ARCH = {"rocm": 150}
#: A cancelled/skipped producer is one queue casualty, not a re-queue loop (issue #2892): each cell
#: gets AT MOST ONE replacement dispatch per trigger run, awaited on the CARRIED budget —
#: `budget * REPLACEMENT_FACTOR` minus the minutes the cancelled attempt consumed, never under
#: REPLACEMENT_MIN_WAIT, and no replacement at all once the carried budget is gone.
REPLACEMENT_FACTOR = 2
REPLACEMENT_MIN_WAIT = 10
#: A single `gh api` call must never hold a poll loop open past its own deadline
#: (issue: a stalled registry/API call blocks `subprocess.run` with no timeout, so
#: the `time.time() > deadline` bound below is never reached and the trigger hung
#: ~69 min past its 60-min DEFAULT_MAX_WAIT on run 42180155072). This caps each
#: subprocess it performs; a timeout yields an empty response so the loop keeps
#: polling until the deadline and then fails with the existing clear message.
SUBPROCESS_TIMEOUT = 30  # seconds a single shell/gh call may take
#: The ceiling of one fan-out wave's shared await bound (issue #3066). Dispatching every cell before
#: awaiting any verdict only helps if the wave can still NAME its unfinished cells inside the
#: dispatched trigger job's own window (engine-build-pr-trigger.yml gives the trigger job 250 min), so
#: the bound sits below it: the script ends the wait and reports the stall instead of the job being
#: cancelled mid-await with no verdict line at all.
FANOUT_MAX_MINUTES = 240


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


def _dispatch_cell(repo: str, branch: str, engine: str, arch: str,
                   gh: str) -> dict:
    """Dispatch engine-build push=true for ONE (engine, arch) cell and name the NEW run (#964 discipline).

    The verdict is NOT awaited here (issue #3066): every `push=true` run joins the one global
    `engine-build-push` FIFO, so a wave must get ALL of its cells queued before any cell is waited on,
    and `_await_cells` owns the waiting. Returns {run_id} when a run appeared, or a failure dict
    (`status: dispatch-failed` / `queued`, `run_id: ""`) when the dispatch never started one.
    `gh workflow run` exit 0 is never a verdict.
    """
    before = _existing_run_ids(repo, gh)
    fields = [f"engine={engine}", "push=true", "moving_tags=false"]  # issue #178: a PR-scoped
    # producer publishes the unique pin only; the run on main is the one that moves :<arch>/:latest.
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
    return {"run_id": wanted}


def _await_cells(repo: str, pending: list[dict], gh: str) -> dict[tuple[str, str], dict]:
    """Await every dispatched cell's verdict in ONE shared poll loop (issue #3066).

    Each entry of `pending` is {key: (engine, arch), run_id, bound_min}; all of them are polled in the
    same loop, so a cell's wait is bounded by the wave's QUEUE rather than by the cells a serial
    dispatch-and-await loop happened to wait on first. Every terminal rule of the old fused seam
    carries here unchanged: a cancelled/skipped producer is terminal (#1931/#1936), `success` is
    terminal even when `status` never reports `completed` (#1994), a 404 on either endpoint is a poll
    race re-read from the run list (#2059), a `pending` run behind the global push group names its
    holder (#917/#1860), and only a genuine wall-clock expiry ends the wait (#1931).
    Returns {(engine, arch): outcome}.
    """
    started = time.time()
    for p in pending:
        p["deadline"] = started + p["bound_min"] * 60
        p["stall_holder"] = ""
        p["last"] = {}
    live = list(pending)
    outcomes: dict[tuple[str, str], dict] = {}
    while live:
        holder = None  # read at most once per sweep, not once per still-pending cell
        for p in list(live):
            run = _run_verdict(repo, p["run_id"], gh)
            p["last"] = run
            # A 404 on the single-run endpoint is a POLL RACE, not a verdict (issue #2059): the run may
            # already have SUCCEEDED while `/actions/runs/<id>` keeps answering 404. `_run_verdict`
            # re-reads it from the run LIST, and if that still yields nothing this poll simply keeps
            # watching — the wall-clock bound below still bounds the wait, and the failure names `404`
            # so a reader can tell a poll race from a real conclusion.
            # A push=true run sits `pending` with 0 jobs and NO heartbeat while it waits behind the
            # global engine-build-push concurrency group (engine-build.yml:80, issue #917/#621). It will
            # never materialise a job until the group holder concludes — a re-dispatch is futile and
            # this trigger must name the holder rather than report a bare "queued/None" (measured stall:
            # #1696 channel 42201352115 behind 42191808660's hung vllm-rocm, 3h+ 0-jobs, issue #1860).
            if run.get("status") in ("pending", "queued") and not p["stall_holder"]:
                if holder is None:
                    holder = _push_group_holder(repo, gh)
                p["stall_holder"] = holder
            # A cancelled/skipped producer is TERMINAL, never something to wait out (issue #1931): a run
            # cancelled mid-wait (concurrency cancel on a newer push) can report `conclusion: "cancelled"`
            # while its `status` never flips to "completed", so concluding on the status field alone polls
            # that corpse forever (measured: trigger run 42326516316 hung in_progress 3.5h on a producer
            # cancelled 12 s after the trigger started, run 42326545643). Stop waiting and name the cause.
            if run.get("conclusion") in ("cancelled", "skipped"):
                outcomes[p["key"]] = {"run_id": p["run_id"], "status": run.get("status"),
                                      "conclusion": run.get("conclusion"),
                                      "cause": f"producer {run['conclusion']} — nothing to wait for"}
                live.remove(p)
                continue
            # A SUCCESS producer is TERMINAL — nothing left to wait for (issue #1994): a run's
            # `conclusion` is only ever populated once the run has finished, so `conclusion:
            # "success"` is the final verdict even when the `status` field the trigger polls is a
            # stale/mid-flight snapshot that never reports "completed" (measured: trigger run
            # 42352054921 hung 3h54m in_progress on producer 42352074711 `{status: completed,
            # conclusion: success, completed_at: null}`). #1936 made `cancelled`/`skipped` terminal;
            # `success` is the green mirror — without it a succeeded producer holds the wave past its
            # wait bound instead of concluding promptly with a verdict.
            if run.get("conclusion") == "success":
                outcomes[p["key"]] = {"run_id": p["run_id"], "status": run.get("status"),
                                      "conclusion": "success", "cause": None}
                live.remove(p)
                continue
            if run.get("status") == "completed":
                guard = ""
                if run.get("conclusion") == "failure":
                    jobs = _gh(repo, f"{p['run_id']}/jobs", "--jq",
                               ".jobs[] | select(.name == \"guard\") | .conclusion")
                    guard = "Y" if "failure" in jobs else "N"
                kwargs = {"run_id": p["run_id"], "status": run.get("status"),
                          "conclusion": run.get("conclusion"), "guard_refused": guard == "Y"}
                if p["stall_holder"] and not run.get("conclusion"):
                    kwargs["stalled_behind"] = p["stall_holder"]
                outcomes[p["key"]] = kwargs
                live.remove(p)
                continue
        # Wall-clock bound (issue #1931), evaluated per cell against ITS OWN deadline inside the shared
        # loop: a producer that NEVER reports a terminal verdict must not hold the wave past its bound.
        # On expiry fail with the run id and its last known status — never a bare "concluded queued/None"
        # that reads like a verdict that never happened.
        for p in [q for q in live if time.time() > q["deadline"]]:
            run = p["last"]
            kwargs = {"run_id": p["run_id"], "status": run.get("status"),
                      "conclusion": run.get("conclusion"), "expired": True,
                      "bound_min": p["bound_min"]}
            # A status of "404" at expiry is a POLL-VISIBILITY failure, not a build result (issue #2059):
            # the producer id never resolved on EITHER endpoint for the whole bound. Name it so a reader
            # can tell this apart from a producer that genuinely concluded and is worth re-reading.
            if run.get("status") == "404" or run.get("message") == "Not Found":
                kwargs["unresolved_404"] = True
            if p["stall_holder"] and not run.get("conclusion"):
                kwargs["stalled_behind"] = p["stall_holder"]
            outcomes[p["key"]] = kwargs
            live.remove(p)
        if not live:
            break
        time.sleep(POLL_SECONDS)
    return outcomes


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



def _published(engine: str, variant: str, digest=None, registry: str = "") -> tuple[bool, str]:
    """Published-skip probe (issue #2892): does this cell's EXACT tag already resolve a registry manifest?

    Same authority as the merged may-arm — `check_engine_pins_published.exact_tags` for the tag,
    `engine_image._digest_http` for the manifest — instead of a second registry read path: a cell that
    is already published needs NO producer, and re-dispatching it re-queues at the back of the
    `engine-build-push` FIFO to re-publish identical layers (measured 2026-11-17: 28 dispatches for
    ~15 distinct cells across reopen cycles). `digest` injects a fake probe in tests (the pattern the
    may-arm's own tests use); `registry` overrides the probe target.
    """
    probe = digest if digest is not None else ei._digest_http
    tag = cpp.exact_tags(engine, variant)
    found, _err = probe(f"{registry or ei.REGISTRY}/{tag}")
    return bool(found), tag


def _wait_budget(arch: str, override: int | None) -> int:
    """Per-arch wait bound (issue #2892): the measured class bound over the general default; an
    explicit `--wait-min` overrides every class exactly as before."""
    if override is not None:
        return override
    return WAIT_MIN_BY_ARCH.get(arch, DEFAULT_MAX_WAIT)


def _fanout_bound(cell_budget: int, wave_budgets: list[int], override: int | None) -> int:
    """The wait bound ONE cell gets inside a fan-out wave (issue #3066).

    Every `push=true` run joins the same global `engine-build-push` FIFO, so a cell's real wait is the
    queue in front of it, not its own build time: with more than one cell dispatching, each cell is
    bounded by `min(FANOUT_MAX_MINUTES, max(cell budget, sum of the wave budgets))` — the wave's own
    queue, capped below the trigger job's window so an unfinished cell is REPORTED (task 1.6) rather
    than cut off by the job timeout. A single dispatching cell keeps its class bound, and an explicit
    `--wait-min` keeps that exact bound for every cell (#2892 semantics unchanged).
    """
    if override is not None:
        return override
    if len(wave_budgets) <= 1:
        return cell_budget
    return min(FANOUT_MAX_MINUTES, max(cell_budget, sum(wave_budgets)))


def _missing_variant(e: str, v: str, outcome: dict, bound: int) -> str:
    """The `MISSING VARIANT` line for a dispatched cell that never reached a verdict (issue #3066).

    The FAIL line says what the producer did; this line says what the REGISTRY does not have: the
    variant this bump repins is unverified as published, and the bump PR body must carry that gap as
    `## Not covered` pointing at its own issue lane rather than a tick the run cannot back.
    """
    run = outcome.get("run_id") or "no producer run"
    return (f"[will] MISSING VARIANT engine={e} arch={v}: the image this bump repins is NOT verified as "
            f"published ({run}, wait bound {bound} min, last status {outcome.get('status')}) — carry it "
            f"as `## Not covered` in the bump PR body with its own issue lane (issue #3066), never as a "
            f"tick this run cannot back")


def check(base: str, engine_filter: str = "", arch: str = "", dry: bool = False, repo: str = "",
          branch: str = "", wait_min: int | None = None, *, digest=None, gh: str = "gh") -> int:
    """Dispatch + await a push=true engine-build for every repinned CELL; 0 when all succeeded.

    One dispatch per cell with `engine=<id> arch=<variant>` (#2590): the explicit arch means
    the producer builds the cell this change repinned, never a cpu-only substitute chosen by
    the matrix default. No repin => print and return 0 with no dispatch (hermetic). `dry`
    prints the plan and never dispatches — and never probes the registry either. Published-skip
    (#2892): a cell whose exact tag already resolves a manifest is announced and NOT dispatched;
    when every cell skipped, the pass is green with zero dispatches. Fan-out (issue #3066): every
    unpublished cell is DISPATCHED before any producer verdict is awaited, cheapest class first, and
    the wave is awaited in ONE shared poll loop — a `push=true` run only ever joins the global
    engine-build-push FIFO, so queuing the whole wave up front is what makes a multi-variant bump cost
    less than the sum of its builds. The wait bound is per-arch (`WAIT_MIN_BY_ARCH` over
    `DEFAULT_MAX_WAIT`; `wait_min` overrides every class) widened to the wave's own queue inside the
    trigger job's window (`FANOUT_MAX_MINUTES`), and a cancelled/skipped producer gets at most ONE
    replacement dispatch on the carried budget. A cell that never reaches a verdict is reported as a
    MISSING VARIANT.
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
            print(f"  would dispatch engine-build push=true moving_tags=false engine={e} arch={v} @ {branch}")
        print("[will] dry-run: nothing dispatched")
        return 0
    failures = 0
    published_skipped = 0
    to_dispatch: list[tuple[str, str]] = []
    for e, v in sorted(cells):
        published, tag = _published(e, v, digest=digest)
        if published:
            # Already in the registry at this exact content tag — dispatching would re-queue this
            # cell at the back of the engine-build-push FIFO to re-publish identical layers (#2892).
            print(f"[will] published-skip engine={e} arch={v}: tag {tag} already resolves a "
                  f"registry manifest — no producer dispatch (issue #2892)")
            published_skipped += 1
            continue
        to_dispatch.append((e, v))
    if published_skipped == len(cells):
        print(f"[will] every repinned cell ({published_skipped}) already published at its exact tag; "
              f"nothing dispatched (issue #2892)")
        return 0

    # FAN-OUT (issue #3066): every unpublished cell is QUEUED before ANY verdict is awaited. A
    # `push=true` run only ever joins the one global `engine-build-push` FIFO, so a wave that dispatches
    # as it awaits pays that queue in series: its tail cell sits behind the builds in front of it and
    # expires on a bound that never covered the wave. Dispatch the whole wave first, then await it in
    # one shared poll loop. Ascending per-arch budget (#2590 keeps the explicit `arch=` per cell) puts
    # the long class LAST in the FIFO, so the cell most likely to run out of time is the tail.
    ordered = sorted(to_dispatch, key=lambda c: (_wait_budget(c[1], wait_min), c[0], c[1]))
    wave = [_wait_budget(v, wait_min) for _, v in ordered]
    if len(wave) > 1:
        print(f"[will] fan-out: {len(wave)} producer dispatches queued before any verdict is awaited "
              f"(issue #3066)")
    pending: list[dict] = []
    outcomes: dict[tuple[str, str], dict] = {}
    bounds: dict[tuple[str, str], int] = {}
    for e, v in ordered:
        budget = _wait_budget(v, wait_min)
        bound = _fanout_bound(budget, wave, wait_min)
        bounds[(e, v)] = bound
        print(f"[will] dispatching engine-build push=true engine={e} arch={v} @ {branch} "
              f"(await bound {bound} min, class budget {budget} min)")
        started = _dispatch_cell(repo, branch, e, v, gh)
        if started.get("run_id"):
            pending.append({"key": (e, v), "run_id": started["run_id"], "bound_min": bound,
                            "t0": time.time()})
        else:
            # A dispatch that never started a producer run has no verdict to await: name it now.
            outcomes[(e, v)] = started
    outcomes.update(_await_cells(repo, pending, gh))

    replacements: list[dict] = []
    replaced: set[tuple[str, str]] = set()
    for entry in pending:
        key = entry["key"]
        outcome = outcomes[key]
        if outcome.get("cause") and outcome.get("conclusion") in ("cancelled", "skipped"):
            # One queue casualty is allowed to cost ONE replacement, never a reopen-driven storm:
            # the cell's total bound is `bound * REPLACEMENT_FACTOR`, and the replacement is awaited
            # on what remains of it (issue #2892). A `guard_refused` outcome has no cause and is
            # never replaced: a policy refusal is not a queue casualty.
            consumed_min = int((time.time() - entry["t0"]) // 60)
            remaining = entry["bound_min"] * REPLACEMENT_FACTOR - consumed_min
            if remaining >= REPLACEMENT_MIN_WAIT:
                replaced.add(key)
                print(f"[will] engine={key[0]} arch={key[1]}: producer {outcome['conclusion']}; "
                      f"dispatching the ONE replacement dispatch permitted per cell (issue #2892) "
                      f"with the carried budget {remaining} min ({entry['bound_min']} x "
                      f"{REPLACEMENT_FACTOR} - {consumed_min} consumed)")
                started = _dispatch_cell(repo, branch, key[0], key[1], gh)
                if started.get("run_id"):
                    replacements.append({"key": key, "run_id": started["run_id"],
                                         "bound_min": remaining, "t0": time.time()})
                else:
                    outcomes[key] = started
    if replacements:
        outcomes.update(_await_cells(repo, replacements, gh))

    for e, v in sorted(to_dispatch):
        key = (e, v)
        outcome = outcomes[key]
        bound = bounds[key]
        # A dispatched cell that did not end `success` is a MISSING VARIANT — expired, stalled behind
        # the holder, refused, cancelled or failed all mean the same thing for the REGISTRY: it does
        # not have this bump's pinned image, so the gap is a `## Not covered` item, never a tick
        # (issue #3066).
        missing = outcome.get("conclusion") != "success"
        note = ""
        if key in replaced and outcome.get("conclusion") != "success":
            note = (f" — the replacement dispatch (issue #2892) also ended {outcome.get('conclusion')}; "
                    f"no further dispatch from this run")
        if outcome.get("guard_refused"):
            print(f"[will] FAIL engine={e} arch={v}: producer refused at its own trigger guard "
                  f"(run {outcome.get('run_id')}) — NOT VERIFIED, not a bare failure", file=sys.stderr)
            failures += 1
        elif outcome.get("cause"):
            print(f"[will] FAIL engine={e} arch={v}: {outcome['cause']} (run {outcome.get('run_id')}){note}",
                  file=sys.stderr)
            failures += 1
        elif outcome.get("error"):
            # A dispatch that never started a producer run has no producer verdict at all. It carries
            # its own reason (`HTTP 422: the workflow input 'arch' is not valid`, an unknown input, a
            # permission refusal) — print it, so the log says which refusal this was instead of a bare
            # `run  concluded queued/None` (issue #2089).
            print(f"[will] FAIL engine={e} arch={v}: the dispatch never started a producer run — "
                  f"{outcome['error']}{note}", file=sys.stderr)
            failures += 1
        elif outcome.get("expired"):
            msg = (f"[will] FAIL engine={e} arch={v}: wait bound ({bound} min) expired — producer run "
                   f"{outcome.get('run_id')} never concluded, last status {outcome.get('status')}")
            if outcome.get("unresolved_404"):
                msg += (" — the producer id never resolved on the run endpoint (404 for the whole bound): "
                        "a POLL-VISIBILITY race, not a build result; re-run the trigger / re-check the run "
                        "by hand before treating this as a failure (issue #2059)")
            if outcome.get("stalled_behind"):
                msg += (f" — STALLED behind engine-build-push group holder run "
                        f"{outcome['stalled_behind']} (that holder must conclude or be owner-cancelled; "
                        f"re-dispatch queues behind the same gate, issue #1860)")
            print(msg + note, file=sys.stderr)
            failures += 1
        elif outcome.get("conclusion") != "success":
            # A rejected dispatch carries its own reason (`HTTP 422: No ref found for: HEAD`, an
            # unknown input, a permission refusal) — print it, so the log says which refusal this
            # was instead of a bare `run  concluded queued/None` (issue #2089).
            extra = f" — {outcome['error']}" if outcome.get("error") else ""
            print(f"[will] FAIL engine={e} arch={v}: run {outcome.get('run_id')} concluded "
                  f"{outcome.get('status')}/{outcome.get('conclusion')}{extra}{note}", file=sys.stderr)
            failures += 1
        else:
            print(f"[will] OK engine={e} arch={v}: producer run {outcome.get('run_id')} success")
        if missing:
            # The FAIL line says what the producer did; this names what the REGISTRY does not have.
            print(_missing_variant(e, v, outcome, bound), file=sys.stderr)
    if failures:
        print(f"[will] {failures} engine-build run(s) did not succeed — the producer must build+push these "
              f"cells before the bump may merge (issue #1633)", file=sys.stderr)
        return 1
    print("[will] every repinned cell's push=true build succeeded"
          + (f" ({published_skipped} published-skip, issue #2892)" if published_skipped else ""))
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
    ap.add_argument("--wait-min", type=int, default=None,
                    help="override the wait bound for EVERY cell (default: per-arch — 60 min, "
                         "rocm %d min, issue #2892)" % WAIT_MIN_BY_ARCH["rocm"])
    ap.add_argument("--gh", default="gh", help="gh binary (tests inject a fake)")
    args = ap.parse_args(argv)
    base = base_ref.resolve_base(explicit=args.base, quiet=True)
    if args.cmd == "report":
        return report(base, args.engine, args.arch)
    return check(base, args.engine, args.arch, args.dry, args.repo, args.branch, args.wait_min,
                 gh=args.gh)


if __name__ == "__main__":
    sys.exit(main())
