#!/usr/bin/env python3
"""The umbrella sweep — one pipeline that exercises every dispatchable pipeline (issue #1102).

There is no single pipeline that triggers all the others, and 16 of 26 workflows are disabled_manually and
invisible from a green board. This module is the engine behind `.github/workflows/all-pipelines.yml`:

- enumerate the checked-out tree's `.github/workflows/*.yml` (the roster is derived from the tree, never a
  hand-kept list);
- classify each: dispatchable (a `workflow_dispatch` trigger), active/disabled (live state via the GitHub
  API), and self (the umbrella, excluded so a sweep of "every dispatchable" does not dispatch itself and
  recurse);
- dispatch every active, dispatchable, non-self workflow and AWAIT each dispatched run's own verdict —
  `gh workflow run` exiting 0 is not a verdict (#964's `gh pr merge --auto` trap applies to dispatch too);
- a disabled workflow is rendered `DISABLED (owner re-enable required)`, excluded from ok/failed, and named
  in a printed excluded list so a green summary can never hide dead pipelines;
- emit the table `workflow · dispatched run id · status/conclusion · completed_at`, state the sha swept, and
  exit non-zero at the END only if any non-disabled dispatched run failed (failure isolation — one red
  pipeline never aborts the sweep).

Commands:
    all_pipelines.py sweep --repo owner/repo [--ref main] [--gh /path/to/gh] [--timeout 300]

The `--gh` knob lets a test drive a stub binary, exactly as ci_requeue's `CI_REQUEUE_GH`.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ".github/workflows"
SELF = "all-pipelines.yml"
DISABLED_MARK = "DISABLED (owner re-enable required)"
# A non-dispatchable ACTIVE workflow (auto-merge, ci, pipeline) cannot be swept: it has no
# `workflow_dispatch`, so the one thing this umbrella can do — dispatch it — is impossible. It is
# reported separately, not counted as ok/failed/disabled.
NOT_DISPATCHABLE_MARK = "NOT DISPATCHABLE (no workflow_dispatch)"
POLL_SECONDS = 15
MAX_ATTEMPTS = 400  # ~100 min of polling per run at 15 s; the workflow's timeout-minutes is the backstop


def _gh(exe_override: str | None = None) -> str:
    """The `gh` binary to drive; `ALL_PIPELINES_GH` overrides it so a test can stub dispatch."""
    return os.environ.get("ALL_PIPELINES_GH") or exe_override or "gh"


def run_gh(args: list[str], gh: str) -> str:
    r = subprocess.run([gh, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"[all-pipelines] gh {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def load_json(text: str):
    """Parse gh `--jq --paginate` output: one compact JSON document PER PAGE, newline-joined.

    `json.loads` on the whole blob raises `Extra data` once a second page arrives; the fix is to treat each
    line as its own document and, where pages are arrays, concatenate them. A query that returns a single
    object (a run's verdict) still parses as one line.
    """
    stripped = text.strip()
    if not stripped:
        return []
    try:
        doc = json.loads(stripped)
        return doc if isinstance(doc, list) else [doc]
    except json.JSONDecodeError:
        merged: list = []
        for line in stripped.splitlines():
            if not line.strip():
                continue
            doc = json.loads(line)
            if isinstance(doc, list):
                merged.extend(doc)
            else:
                merged.append(doc)
        return merged


def workflow_files(root: Path = REPO_ROOT) -> list[str]:
    """The tree's workflow files, sorted — the roster the sweep derives (never a fixed list)."""
    return sorted(p.name for p in (root / WORKFLOWS).glob("*.yml"))


def workflow_states(repo: str, gh: str) -> dict[str, dict]:
    """`{file: {state, id, active}}` from `gh api repos/{repo}/actions/workflows` (one call)."""
    raw = run_gh(["api", f"repos/{repo}/actions/workflows", "--paginate", "--jq",
                  ".workflows[] | {path: .path, state: .state, id: (.id|tostring)}"], gh)
    out: dict[str, dict] = {}
    for w in load_json(raw):
        out[Path(w["path"]).name] = {"state": w["state"], "id": w["id"],
                                     "active": w["state"] == "active"}
    return out


def is_dispatchable(path: Path) -> bool:
    """Does the workflow declare a `workflow_dispatch` trigger under a top-level `on:` block?"""
    text = path.read_text()
    on_idx = None
    for n, line in enumerate(text.splitlines()):
        if line.strip() == "on:":
            on_idx = n
            break
    if on_idx is None:
        return False
    # keys under `on:` are indented 2 spaces; `workflow_dispatch:` is one of them
    for line in text.splitlines()[on_idx + 1:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip()) if line.strip() else 0
        if indent == 0:
            break                      # left `on:` block — not declared
        if line.strip() == "workflow_dispatch" or line.strip().startswith("workflow_dispatch:"):
            return True
    return False


def classify(root: Path, states: dict[str, dict]) -> list[dict]:
    """`[{file, role: dispatch|disabled|not_dispatchable|self, id, active}]` from the tree + live states.

    A file not present in the API response (brand-new, or the API is a step behind the tree) is treated as
    active: dispatching it fails loudly if it truly cannot run, and a sweep that silently skips a new
    pipeline is exactly the blindness this change exists to stop.
    """
    rows: list[dict] = []
    for name in workflow_files(root):
        path = root / WORKFLOWS / name
        st = states.get(name)
        active = st["active"] if st else True
        dispatchable = is_dispatchable(path)
        if name == SELF:
            role = "self"
        elif active and dispatchable:
            role = "dispatch"
        elif active and not dispatchable:
            role = "not_dispatchable"
        else:
            role = "disabled"
        rows.append({"file": name, "role": role, "id": (st or {}).get("id", ""), "active": active,
                     "dispatchable": dispatchable})
    return rows


def existing_run_ids(repo: str, gh: str, wf_id: str) -> set[str]:
    """Run ids already present for this workflow, so the dispatched run can be identified as NEW.

    `gh api repos/{repo}/actions/workflows/{id}/runs` returns `.workflow_runs` (each `.id`). A failed call
    (a brand-new workflow GH has not listed yet) means "no prior runs" — dispatching will still surface the
    new one.
    """
    try:
        raw = run_gh(["api", f"repos/{repo}/actions/workflows/{wf_id}/runs", "--paginate",
                      "--jq", ".workflow_runs[] | (.id|tostring)"], gh)
    except SystemExit:
        return set()
    return set(raw.splitlines())


def wait_for_dispatched_run(repo: str, gh: str, wf_id: str, before: set[str],
                            timeout: int) -> dict:
    """The run id this dispatch created: a workflow_dispatch-event run for this workflow not present before,
    within `timeout` seconds. Returns `{workflow_id, status, conclusion, completed_at, run_id}`.
    `gh workflow run` returns 0 whether or not a real run started (the #964 trap), so the NEW run's own
    verdict is the fact — never the dispatch exit code."""
    t0 = time.time()
    wanted: str | None = None
    while wanted is None:
        if time.time() - t0 > timeout:
            raise SystemExit(f"[all-pipelines] no workflow_dispatch run appeared for workflow id {wf_id} "
                             f"within {timeout}s — dispatch may have been refused; check the dispatch guard")
        raw = run_gh(["api", f"repos/{repo}/actions/runs", "--paginate",
                      "--jq", ".workflow_runs[] | select(.event == \"workflow_dispatch\") | "
                              "{id: (.id|tostring), workflow_id: ((.workflow_id // \"\")|tostring)}"],
                     gh)
        for r in load_json(raw):
            if r.get("workflow_id") == wf_id and r.get("id") not in before:
                wanted = r["id"]
                break
        if wanted is None:
            time.sleep(5)
    # Now await THAT run's verdict.
    while True:
        run = load_json(run_gh(["api", f"repos/{repo}/actions/runs/{wanted}",
                                "--jq", "{status, conclusion, completed_at}"], gh))[0]
        if run["status"] == "completed" or time.time() - t0 > MAX_ATTEMPTS * POLL_SECONDS:
            return {"run_id": wanted, **run}
        time.sleep(POLL_SECONDS)


def dispatch_one(repo: str, gh: str, wf_file: str, wf_id: str, ref: str, timeout: int) -> dict:
    """Dispatch `wf_file` and await its run's verdict. `gh workflow run` exit 0 is not a verdict."""
    before = existing_run_ids(repo, gh, wf_id)
    run_gh(["workflow", "run", wf_file, "--repo", repo, "--ref", ref], gh)
    return wait_for_dispatched_run(repo, gh, wf_id, before, timeout)


def ok(row: dict, concluded: dict | None) -> str:
    """The table cell for this row's outcome, or a marker."""
    if row["role"] == "disabled":
        return DISABLED_MARK
    if row["role"] == "not_dispatchable":
        return NOT_DISPATCHABLE_MARK
    if row["role"] == "self":
        return "(the sweep itself — not re-dispatched)"
    if concluded is None:
        return "did not run"
    return f"{concluded['status']}/{concluded['conclusion'] or 'none'}"


def render_report(rows: list[dict], concluded: dict[str, dict], sha: str) -> tuple[str, int]:
    """The table `workflow | dispatched run id | status/conclusion | completed_at`, the excluded list and
    the `N ok · M failed · K disabled` summary. Returns (text, exit_code).

    exit_code is 1 iff any DISPATCHED (non-disabled, non-self, non-not_dispatchable) run failed —
    computed at the END, so the full table is always emitted (failure isolation).
    """
    lines = [f"# all-pipelines sweep @ {sha}", "", "| workflow | dispatched run id | status/conclusion | completed_at |",
             "|---|---|---|---|", ""]
    excluded_disabled: list[str] = []
    excluded_nd: list[str] = []
    failed = 0
    for row in rows:
        c = concluded.get(row["file"])
        outcome = ok(row, c)
        run_id = c["run_id"] if c and row["role"] == "dispatch" else "—"
        completed = (c.get("completed_at") or "—") if (c and row["role"] == "dispatch") else "—"
        lines.append(f"| `{row['file']}` | {run_id} | {outcome} | {completed} |")
        if row["role"] == "disabled":
            excluded_disabled.append(row["file"])
        elif row["role"] == "not_dispatchable":
            excluded_nd.append(row["file"])
    ok_n = sum(1 for row in rows if row["role"] == "dispatch"
               and concluded.get(row["file"]) and concluded[row["file"]]["conclusion"] == "success")
    failed_n = sum(1 for row in rows if row["role"] == "dispatch"
                   and concluded.get(row["file"]) and concluded[row["file"]][
                       "conclusion"] not in (None, "success"))
    failed = sum(1 for row in rows if row["role"] == "dispatch"
                 and concluded.get(row["file"]) and concluded[row["file"]][
                     "conclusion"] not in (None, "success"))
    disabled_n = sum(1 for row in rows if row["role"] == "disabled")
    lines.append("")
    lines.append(f"Summary: {ok_n} ok · {failed} failed · {disabled_n} disabled")
    if excluded_disabled:
        lines.append("")
        lines.append("Excluded — disabled (owner re-enable required):")
        lines.append(", ".join(f"`{f}`" for f in excluded_disabled))
    if excluded_nd:
        lines.append("")
        lines.append("Not dispatchable (no workflow_dispatch) — not swept:")
        lines.append(", ".join(f"`{f}`" for f in excluded_nd))
    return "\n".join(lines) + "\n", 1 if failed else 0


def sweep(repo: str, ref: str, gh: str, timeout: int, root: Path = REPO_ROOT) -> tuple[str, int]:
    """Drive the sweep; returns (report, exit_code)."""
    states = workflow_states(repo, gh)
    rows = classify(root, states)
    concluded: dict[str, dict] = {}
    sha = ""
    try:  # the sha of the tree being swept (acceptance #4)
        sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                             cwd=root).stdout.strip()
    except Exception:
        sha = "unknown"
    for row in rows:
        if row["role"] != "dispatch":
            continue
        concluded[row["file"]] = dispatch_one(repo, gh, row["file"], row["id"], ref, timeout)
    report, code = render_report(rows, concluded, sha)
    print(report)
    return report, code


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sweep", nargs="?", help="run the sweep")
    ap.add_argument("--repo", required=True, help="owner/repo (the repo whose workflows are swept)")
    ap.add_argument("--ref", default="main", help="branch/ref the umbrella dispatches other workflows at")
    ap.add_argument("--gh", default=None, help="path to the gh binary (default: gh on PATH / ALL_PIPELINES_GH)")
    ap.add_argument("--timeout", type=int, default=120, help="seconds to wait for a run to appear after dispatch")
    a = ap.parse_args(argv)
    report, code = sweep(a.repo, a.ref, _gh(a.gh), a.timeout)
    return code


if __name__ == "__main__":
    sys.exit(main())
