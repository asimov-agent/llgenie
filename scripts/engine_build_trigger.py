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
        return subprocess.run(args, capture_output=True, text=True,
                              timeout=SUBPROCESS_TIMEOUT).stdout  # proc-allow: direct subprocess call site, tracked remainder for issue #797
    except subprocess.TimeoutExpired:
        return ""  # no verdict this poll; the caller's deadline check decides


def _gh(repo: str, *args: str, gh: str = "gh") -> str:
    return _sh([gh, "api", f"repos/{repo}/actions/runs" + (args[0] if args else ""), *args[1:]])


def repinned(base: str, engine_filter: str = "") -> list[str]:
    """Engine ids this change repins vs `base`, optionally narrowed to one engine."""
    ids = [e for e in cpp.repinned_engine_ids(base) if not engine_filter or e == engine_filter]
    return ids


def _existing_run_ids(repo: str, gh: str) -> set[str]:
    """workflow_dispatch run ids for engine-build currently known (before our dispatch)."""
    raw = _gh(repo, "?per_page=100", "--jq",
              '.workflow_runs[] | select(.event == "workflow_dispatch") | '
              'select(.path == "/.github/workflows/engine-build.yml") | .id | tostring', gh=gh)
    return {line.strip() for line in raw.splitlines() if line.strip()}


def _dispatch_and_wait(repo: str, branch: str, engine: str, arch: str,
                       wait_min: int, gh: str) -> dict:
    """Dispatch engine-build push=true for ONE engine, await the NEW run's own verdict (#964 discipline).

    Returns {run_id, status, conclusion, guard_refused}. `gh workflow run` exit 0 is never a verdict.
    """
    before = _existing_run_ids(repo, gh)
    fields = [f"engine={engine}", "push=true"]
    if arch:
        fields.append(f"arch={arch}")
    try:
        subprocess.run([gh, "workflow", "run", ENGINE_BUILD_WORKFLOW, "--repo", repo, "--ref", branch,  # proc-allow: engine-build dispatch is a deliberate CLI dispatch on the seam's tracked remainder (#797); check=False is required because gh workflow run exit 0 is not a verdict (the NEW run is awaited below, #964)
                        "--field", *[f for f in fields]], check=False, timeout=SUBPROCESS_TIMEOUT)
    except subprocess.TimeoutExpired:
        # The dispatch call itself stalled; the discovery loop below still looks for the
        # NEW workflow_dispatch run (the real verdict) and bails at DISPATCH_TIMEOUT.
        pass
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
    while True:
        raw = _gh(repo, f"{wanted}", "--jq", "{status, conclusion, completed_at}")
        try:
            run = json.loads(raw)
        except json.JSONDecodeError:
            run = {}
        if run.get("status") == "completed" or time.time() > deadline:
            guard = ""
            if run.get("conclusion") == "failure":
                jobs = _gh(repo, f"{wanted}/jobs", "--jq",
                           ".jobs[] | select(.name == \"guard\") | .conclusion")
                guard = "Y" if "failure" in jobs else "N"
            return {"run_id": wanted, "status": run.get("status"), "conclusion": run.get("conclusion"),
                    "guard_refused": guard == "Y"}
        time.sleep(POLL_SECONDS)


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
    branch = branch or _sh(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip().strip()
    print(f"[will] {len(ids)} repinned engine(s) vs {base}: {', '.join(sorted(ids))}")
    if dry:
        for e in sorted(ids):
            print(f"  would dispatch engine-build push=true engine={e}{f' arch={arch}' if arch else ''} @ {branch}")
        print("[will] dry-run: nothing dispatched")
        return 0
    failures = 0
    for e in sorted(ids):
        print(f"[will] dispatching engine-build push=true engine={e}{f' arch={arch}' if arch else ''} @ {branch}")
        outcome = _dispatch_and_wait(repo, branch, e, arch, wait_min, gh)
        if outcome.get("guard_refused"):
            print(f"[will] FAIL engine={e}: producer refused at its own trigger guard "
                  f"(run {outcome.get('run_id')}) — NOT VERIFIED, not a bare failure", file=sys.stderr)
            failures += 1
        elif outcome.get("conclusion") != "success":
            print(f"[will] FAIL engine={e}: run {outcome.get('run_id')} concluded "
                  f"{outcome.get('status')}/{outcome.get('conclusion')}", file=sys.stderr)
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
