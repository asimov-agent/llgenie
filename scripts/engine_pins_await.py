#!/usr/bin/env python3
"""Await the engine image producer this lane itself started, BEFORE the pins gate reads GHCR.

Part of issue #3051 (the pins-gate race). An engine-bump PR repins the tag identity of
`containers/engines/params/<engine>.json` cells (`check_engine_pins_published.repinned_engine_ids`
names them), and the images for those tags are published by
`engine-build-pr-trigger.yml` — a SEPARATE workflow, so GitHub `needs:` can never order the unit
battery after it. `make check-engine-pins-published` (step 15/54 of `make ci-unit`) therefore read
a registry snapshot taken before the producer published anything and reddened the battery with
`HTTP Error 404` findings for tags the same lane was still building (measured 2026-11-24T06:20Z on
PR #3030 head `20b3f0307`: pins step failed at `19:08:53Z`, the producer job ran to `20:50:34Z`).

This script gives the ordering the workflow graph cannot: the CI lane runs
`make engine-pins-await` immediately BEFORE `make ci-unit`, so the pins step is evaluated after the
lane's own producer has concluded — or after a bounded window closed, in which case
`check_engine_pins_published.py` reports the unresolved repinned refs as `PINS-PENDING` rather than
pretending they are built.

Discipline it must keep (AGENTS.md):

- **Read-only.** It lists this repository's `engine-build-pr-trigger` runs through `gh api` and
  reads their status. It never dispatches, never re-triggers, never re-runs, never cancels — a
  wedge is fixed by pushing a commit, never by pumping the queue.
- **Bounded.** `ENGINE_PINS_AWAIT_SECONDS` (default 0) caps the wait: an unconfigured call looks the
  producer up once and returns. A CI lane sets a window, never an unbounded sleep.
- **Never reddens anything.** Every outcome exits 0, including "nothing this change repins" and
  "the window expired with the producer still running". The verdict belongs to the pins gate, which
  reads the state the await produced.

Usage:

    make engine-pins-await BASE=origin/main
    ENGINE_PINS_AWAIT_SECONDS=2700 make engine-pins-await   # the CI lane's setting
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import base_ref  # noqa: E402
from check_engine_pins_published import repinned_engine_ids  # noqa: E402
from proc import run_ok  # noqa: E402  # the ONE subprocess policy seam (issue #797)

REPO = Path(__file__).resolve().parent.parent
PRODUCER_WORKFLOW = "engine-build-pr-trigger.yml"
DEFAULT_WINDOW_SECONDS = 0.0
POLL_SECONDS = 30.0
#: One `gh api` GET is capped: a hung read is a `WARN` the pins gate decides past, never a wedge.
GH_API_TIMEOUT_SECONDS = 60.0


def _gh_api(path: str) -> dict:
    """One read-only `gh api` GET through `scripts/proc.py` (issue #797).

    No verb argument is ever passed: reads only. `run_ok` never raises on a non-zero exit, so the
    failure is reported by THIS seam with the command's stderr, not swallowed into an empty read.
    """
    proc = run_ok(["gh", "api", path], timeout=GH_API_TIMEOUT_SECONDS)
    if proc.returncode != 0:
        raise RuntimeError(f"gh api {path} failed: {(proc.stderr or '').strip()[:300]}")
    return json.loads(proc.stdout or "{}")


def run_lookup(repo: str, workflow: str) -> list[dict]:
    """The producer workflow's recent runs for this repository (newest first)."""
    data = _gh_api(f"repos/{repo}/actions/workflows/{workflow}/runs?per_page=20")
    return list(data.get("workflow_runs") or [])


def _in_progress(run: dict) -> bool:
    return str(run.get("status") or "") != "completed"


def _dispatch_runs(runs: list[dict], head_sha: str, head_ref: str) -> list[dict]:
    """The producer runs that belong to THIS lane.

    `engine-build-pr-trigger` is a `workflow_dispatch` lane started by the PR's own trigger step, so
    its runs carry the PR's head BRANCH (`head_branch == GITHUB_HEAD_REF`) and the PR head sha — not
    this job's `GITHUB_SHA`, which on a `pull_request` event is the merge commit. Matching is therefore
    by branch OR sha, plus the `refs/pull/N/head` ref a dispatch against the PR carries. Runs from other
    heads are not this lane's producer and are never waited on; with no ref or sha known (a local run)
    every recent dispatch of the workflow is treated as in-scope, which is the conservative read.
    """
    out = []
    stem = PRODUCER_WORKFLOW.removesuffix(".yml")
    for run in runs:
        path = str(run.get("path") or "")
        name = str(run.get("name") or "")
        # The runs API is already scoped to the workflow file, but the display NAME of a run is its
        # `name:` line (truncated), NOT the file name — matching on `name` silently drops every real
        # run. Match the file `path`, fall back to a name prefix only when the API omits it.
        if path and path != PRODUCER_WORKFLOW and not path.endswith(f"/{PRODUCER_WORKFLOW}"):
            continue
        if not path and not name.startswith(stem):
            continue
        sha = str(run.get("head_sha") or "")
        ref = str(run.get("head_branch") or "")
        if head_ref and ref == head_ref:
            out.append(run)
            continue
        if head_sha and sha and sha == head_sha:
            out.append(run)
            continue
        if ref.startswith("refs/pull/"):
            out.append(run)
            continue
        if not head_ref and not head_sha:
            out.append(run)
    return out


def await_producer(base: str,
                   *,
                   repo: str | None = None,
                   workflow: str = PRODUCER_WORKFLOW,
                   seconds: float | None = None,
                   lookup: Callable[[str, str], list[dict]] | None = None,
                   sleep: Callable[[float], None] = time.sleep,
                   clock: Callable[[], float] = time.monotonic,
                   head_sha: str | None = None,
                   head_ref: str | None = None,
                   poll_seconds: float = POLL_SECONDS) -> int:
    """Poll this lane's producer until it concludes or the window closes. Always exit 0."""
    ids = repinned_engine_ids(base)
    if not ids:
        print("[await] no engine this change repins; nothing to await (issue #3051)")
        return 0

    repo = repo or os.environ.get("GITHUB_REPOSITORY", "")
    head_sha = head_sha if head_sha is not None else os.environ.get("GITHUB_SHA", "")
    head_ref = head_ref if head_ref is not None else (
        os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME") or "")
    if not repo:
        print("[await] WARN GITHUB_REPOSITORY is unset; cannot look the producer up — the pins "
              "gate decides on its own (issue #3051)", file=sys.stderr)
        return 0

    if seconds is None:
        raw = os.environ.get("ENGINE_PINS_AWAIT_SECONDS", str(DEFAULT_WINDOW_SECONDS))
        try:
            seconds = max(0.0, float(raw))
        except ValueError:
            print(f"[await] WARN ENGINE_PINS_AWAIT_SECONDS={raw!r} is not a number; not waiting "
                  "(issue #3051)", file=sys.stderr)
            seconds = 0.0

    fetch = lookup if lookup is not None else run_lookup
    print(f"[await] repinned engine(s): {', '.join(ids)}; awaiting {workflow} runs for {repo}")

    def _live() -> list[dict] | None:
        try:
            return _dispatch_runs(fetch(repo, workflow), head_sha, head_ref)
        except Exception as exc:  # never redden the lane: the pins gate keeps the verdict
            print(f"[await] WARN could not read {workflow} runs "
                  f"({type(exc).__name__}: {str(exc)[:180]}); the pins gate decides on its own "
                  f"(issue #3051)", file=sys.stderr)
            return None

    live = _live()
    if live is None:
        return 0
    if not live:
        print(f"[await] no {workflow} run for this head; nothing to await")
        return 0

    deadline = clock() + seconds
    seen: dict[int, str] = {}
    pending = [run for run in live if _in_progress(run)]
    for run in live:
        if not _in_progress(run):
            key = int(run.get("id") or 0)
            seen[key] = f"completed/{run.get('conclusion')}"
            print(f"[await] PRODUCER {key} already {seen[key]}")
    while pending:
        for run in pending:
            key = int(run.get("id") or 0)
            state = f"{run.get('status')}/{run.get('conclusion')}"
            if seen.get(key) != state:
                seen[key] = state
                print(f"[await] AWAIT {key} {state}")
        if clock() >= deadline:
            print(f"[await] AWAIT WINDOW-EXPIRED after {seconds:.0f}s with {len(pending)} "
                  f"producer run(s) still in progress; the pins gate reports them PENDING "
                  f"(issue #3051)")
            return 0
        sleep(max(1.0, min(poll_seconds, deadline - clock())))
        live = _live()
        if live is None:
            return 0
        # Record what the new poll actually observed, concluded states included: the DONE report
        # must describe the producer state the pins gate is about to read, not the first snapshot.
        for run in live:
            key = int(run.get("id") or 0)
            state = f"{run.get('status')}/{run.get('conclusion')}"
            if seen.get(key) != state:
                seen[key] = state
                print(f"[await] AWAIT {key} {state}")
        pending = [run for run in live if _in_progress(run)]

    concluded = sorted(seen.items())
    print(f"[await] AWAIT DONE {len(concluded)} producer run(s) concluded"
          f"{': ' + ', '.join(f'{k} {v}' for k, v in concluded) if concluded else ''}; "
          f"the pins gate now reads their published state")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="", help="base ref the repin diff is measured against")
    ap.add_argument("--workflow", default=PRODUCER_WORKFLOW)
    ap.add_argument("--seconds", default=None, help="bounded await window (default "
                                                    "ENGINE_PINS_AWAIT_SECONDS, else 0)")
    args = ap.parse_args(argv)
    base = base_ref.resolve_base(explicit=args.base, quiet=True) or "origin/main"
    return await_producer(base, workflow=args.workflow,
                          seconds=(float(args.seconds) if args.seconds else None))


if __name__ == "__main__":
    sys.exit(main())
