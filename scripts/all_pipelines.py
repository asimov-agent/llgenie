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
- the SECURITY ADMISSION GATE is the one exception: `security-scan.yml` disabled_manually (or with no
  recent run — never-ran within the daily cadence) is NOT a benign DISABLED row. A down daily scan means
  main has no answer to "is a package old today", and a green summary that hides it is the silent gap issue
  #1285 exists to close — so the gate renders `ADMISSION GATE DOWN` and FAILS the sweep (issue #1285);
- emit the table `workflow · dispatched run id · status/conclusion · completed_at`, state the sha swept, and
  exit non-zero at the END only if any non-disabled dispatched run failed or the admission gate is down
  (failure isolation — one red pipeline never aborts the sweep).

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
from datetime import datetime, timezone
from pathlib import Path

import tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ".github/workflows"
SELF = "all-pipelines.yml"
DISABLED_MARK = "DISABLED (owner re-enable required)"
FORBIDDEN_DISABLED_MARK = "FORBIDDEN DISABLED (never pause — issue #902)"
ADMISSION_DOWN_MARK = "ADMISSION GATE DOWN (issue #1285)"
ADMISSION_STALE_MARK = "ADMISSION GATE STALE — no scan within the daily cadence (issue #1285)"
SWEEP_UNSEEN_MARK = "SWEEP UNSEEN (issue #1291)"
# The SECURITY ADMISSION GATE: the daily vulnerability scan (`security-scan.yml`). It is the ONE
# workflow whose `disabled_manually` (or never-ran) state is a RED industrial alarm, not a benign
# DISABLED row — a down daily scan leaves main with no answer to "is a package old today", and the
# all-pipelines sweep is the guard that must say so (issue #1285). The file name is the tree's own
# workflow file, the same stable identifier every other classification uses; it is not a hand-kept
# roster that must be extended when a new scanner arrives — it is the single daily security pipeline.
SECURITY_GATE = "security-scan.yml"
# A healthy daily scan (04:05 UTC schedule) always has a run within ~1 day; "never ran recently"
# means the gate is genuinely not answering. Allow one missed daily slot + a margin, so a scan whose
# cron is silently broken (but did not get disabled) is still caught without false-reds on scheduler
# jitter. This is the freshness half of the admission alarm (issue #1285).
ADMISSION_GATE_MAX_AGE_HOURS = 50
# The observatory of observatories (issue #1291): the #1289 daily-scan alarm only reaches a reader when the
# WEEKLY all-pipelines sweep runs AND is read, so the sweep itself must prove it recently completed — a
# weekly sweep older than its cadence means "no one has asked this week" and is admission-stale exactly like
# an aged daily scan. The sweep's own cadence is 7 days (Saturday 04:27 UTC, cron `27 4 * * 6`); allow one
# missed weekly slot + a margin so a suspended cron is a red while scheduler jitter is not. This is the 
# sweep-self-freshness window, deliberately a superset of the daily 50 h because it guards a WEEKLY run.
SWEEP_GATE_MAX_AGE_HOURS = 24 * 8  # weekly cadence (~168 h) + one missed slot + a margin
# The `never_pause` set is DERIVED from bots/pause.toml (issue #902), never a hand-kept list here:
# #874 established that auto-merge must never be paused, and #902 extends it to every workflow that
# turns a green PR into a mergeable, tested, published one. A hand-listed tuple here is the roster
# defect of issue #301 — if someone adds a merge-path workflow without recording it in the pause
# data, this guard must start protecting it, not silently keep an old list.
_NEVER_PAUSE = frozenset(
    tomllib.loads((REPO_ROOT / "bots" / "pause.toml").read_text())["never_pause"])

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


def security_gate_last_run(repo: str, gh: str, wf_id: str) -> str:
    """The security gate's most recent run `created_at` (ISO-8601), or '' if it has never run.

    The freshness half of the #1285 admission alarm: a gate that is NOT disabled_manually but whose
    schedule has silently stopped firing still leaves main with no clean-scan proof. `gh run list`
    for the workflow (`/actions/workflows/{id}/runs`) answers newest-first; an empty list (never ran)
    or a failed call (brand-new workflow) both mean "no clean-scan evidence" — return '' so the caller
    treats absence of a run exactly like a stale one. The jq extracts `.workflow_runs[0].created_at`;
    a stub that does not emulate `--jq` returns the whole JSON document, so parse defensively either way.
    """
    try:
        raw = run_gh(["api", f"repos/{repo}/actions/workflows/{wf_id}/runs", "--jq",
                      ".workflow_runs[0].created_at"], gh)
    except SystemExit:
        return ""
    text = raw.splitlines()[-1].strip() if raw.splitlines() else ""
    if not text:
        return ""
    try:  # stub shape: {"workflow_runs": [{"created_at": "..."}]}
        doc = json.loads(text)
        runs = doc.get("workflow_runs") if isinstance(doc, dict) else None
        if runs:
            return str(runs[0].get("created_at") or "")
        return ""
    except json.JSONDecodeError:
        return text  # real gh already applied --jq: the line IS the ISO-8601 timestamp


def sweep_self_last_run(repo: str, gh: str, wf_id: str) -> tuple[str, str]:
    """(created_at, head_sha) of the sweep's own MOST RECENT COMPLETED run, or ('', '').

    The observatory-of-observatories half of the #1289/ADMISSION alarm (issue #1291): the daily-scan
    alarm only ever reaches a reader through the weekly all-pipelines sweep, so this sweep itself must
    prove it recently ran — otherwise a down daily scanner sits un-alarmed for up to a week AND a broken
    sweep reads identically to a clean one. We read the sweep's own `/actions/workflows/{id}/runs`
    newest-first, but filter to COMPLETED runs: the sweep is RUNNING right now, so the newest run is this
    in-progress one (age ~0, never stale) and the real question is how long since the previous COMPLETED
    sweep finished. An empty list (never completed) or a failed call both mean "no completed-sweep
    evidence" — ('', '') so the caller treats absence exactly like a stale completed run. The jq extracts
    `created_at` AND `head_sha` (the alarm names the sha a reader can go look at); a stub that does not
    emulate `--jq` returns the whole document, so parse defensively either way.
    """
    try:
        raw = run_gh(["api", f"repos/{repo}/actions/workflows/{wf_id}/runs", "--jq",
                      "[ .workflow_runs[] | select(.status == \"completed\") "
                      "| {created_at, head_sha} ][0]"], gh)
    except SystemExit:
        return "", ""
    text = raw.splitlines()[-1].strip() if raw.splitlines() else ""
    if not text:
        return "", ""
    try:  # real gh already applied --jq: the line IS the singular {created_at, head_sha} object
        doc = json.loads(text)
        if isinstance(doc, dict):
            runs = doc.get("workflow_runs") if "workflow_runs" in doc else None
            if runs is not None:  # stub did not apply --jq: a full {"workflow_runs": [...]} document
                for r in runs:
                    if (r.get("status") or "completed") == "completed":
                        return str(r.get("created_at") or ""), str(r.get("head_sha") or "")
                return "", ""
            return str(doc.get("created_at") or ""), str(doc.get("head_sha") or "")
        return "", ""
    except json.JSONDecodeError:
        try:  # a stub that returns the whole document as one JSON line, healthily completed
            doc = json.loads(text)
            runs = doc.get("workflow_runs") if isinstance(doc, dict) else None
            if runs:
                for r in runs:
                    if (r.get("status") or "completed") == "completed":
                        return str(r.get("created_at") or ""), str(r.get("head_sha") or "")
        except json.JSONDecodeError:
            pass
    return "", ""


def _age_hours(created_at: str) -> float:
    """Hours between an ISO-8601 run timestamp (from the API) and now."""
    t = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - t).total_seconds() / 3600.0


def classify(root: Path, states: dict[str, dict]) -> list[dict]:
    """`[{file, role: dispatch|disabled|not_dispatchable|self|admission_down, id, active}]` from the tree + live states.

    `sweep()` later demotes the SELF row to `sweep_unseen` when the sweep's own last completed run has aged past
    its weekly cadence, and demotes an ACTIVE security gate to `admission_stale` when its last run is too old
    (issue #1285/#1291) — classify returns the static tree+state roles; the freshness demotions own the time axis.

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
        elif name == SECURITY_GATE and not active:
            # The security admission gate disabled is a RED alarm, not a benign DISABLED row (issue
            # #1285): a down daily scan leaves main with no "is a package old today" answer, and the
            # sweep is the one guard the board reads. Marking it `admission_down` (instead of
            # `disabled`) is what makes the sweep fail loudly for THIS workflow and nothing else.
            role = "admission_down"
        elif active and dispatchable:
            role = "dispatch"
        elif active and not dispatchable:
            role = "not_dispatchable"
        elif name in _NEVER_PAUSE:
            role = "forbidden_disabled"
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
    if row["role"] == "forbidden_disabled":
        return FORBIDDEN_DISABLED_MARK
    if row["role"] == "admission_down":
        return ADMISSION_DOWN_MARK
    if row["role"] == "admission_stale":
        return ADMISSION_STALE_MARK
    if row["role"] == "sweep_unseen":
        return SWEEP_UNSEEN_MARK
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
    forbidden: list[str] = []
    admission_down: list[str] = []
    sweep_unseen: list[dict] = []
    failed = 0
    for row in rows:
        c = concluded.get(row["file"])
        outcome = ok(row, c)
        run_id = c["run_id"] if c and row["role"] == "dispatch" else "—"
        completed = (c.get("completed_at") or "—") if (c and row["role"] == "dispatch") else "—"
        lines.append(f"| `{row['file']}` | {run_id} | {outcome} | {completed} |")
        if row["role"] == "admission_down":
            admission_down.append(row["file"])
        elif row["role"] == "admission_stale":
            admission_down.append(row["file"])
        elif row["role"] == "forbidden_disabled":
            forbidden.append(row["file"])
        elif row["role"] == "sweep_unseen":
            sweep_unseen.append(row)
        elif row["role"] == "disabled":
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
    lines.append(f"Summary: {ok_n} ok · {failed} failed · {disabled_n} disabled"
                 f" · {len(forbidden)} FORBIDDEN disabled · {len(admission_down)} ADMISSION GATE DOWN"
                 f" · {len(sweep_unseen)} SWEEP UNSEEN")
    if admission_down:
        lines.append("")
        lines.append(f"ADMISSION GATE DOWN (issue #1285 — the daily security scan is not answering,"
                     f" so main has no clean-scan proof): {', '.join(f'`{a}`' for a in admission_down)}")
    if sweep_unseen:
        lines.append("")
        for row in sweep_unseen:
            last_run = row.get("sweep_last_run") or "never"
            last_sha = row.get("sweep_last_sha") or "?"
            lines.append(f"SWEEP UNSEEN (issue #1291 — the weekly admission sweep has not completed within its "
                         f"cadence, so a down daily scan sits un-alarmed): last completed run "
                         f"{last_run} @ {last_sha} — `{row['file']}`")
    if forbidden:
        lines.append("")
        lines.append("FORBIDDEN disabled (issue #902 — these must never be paused, the merge path "
                     "is how a green PR becomes a merged one):")
        lines.append(", ".join(f"`{f}`" for f in forbidden))
    if excluded_disabled:
        lines.append("")
        lines.append("Excluded — disabled (owner re-enable required):")
        lines.append(", ".join(f"`{f}`" for f in excluded_disabled))
    if excluded_nd:
        lines.append("")
        lines.append("Not dispatchable (no workflow_dispatch) — not swept:")
        lines.append(", ".join(f"`{f}`" for f in excluded_nd))
    return "\n".join(lines) + "\n", 1 if (failed or forbidden or admission_down or sweep_unseen) else 0


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
    # The freshness half of the #1285 admission alarm: an ACTIVE security gate that silently stopped
    # producing runs is as unsafe as a disabled one. A `disabled_manually` gate is already
    # `admission_down` from classify; here we also demote an active gate with no run within the daily
    # cadence (a broken cron never re-fires a run, but never flips the state to disabled_manually) so
    # the board cannot read a silently-silent scanner as "scanned clean".
    for row in rows:
        if row["file"] == SECURITY_GATE and row["role"] in ("dispatch", "not_dispatchable"):
            last = security_gate_last_run(repo, gh, row["id"])
            if not last or _age_hours(last) > ADMISSION_GATE_MAX_AGE_HOURS:
                row["role"] = "admission_stale"
    # The observatory-of-observatories half (issue #1291): the daily-scan alarm above only ever reaches a
    # reader through THIS sweep, so the sweep itself must prove it recently ran. A sweep whose last COMPLETED
    # run has aged past the weekly cadence (or that has never completed) is admission-stale exactly like an
    # aged daily scan — the board has no one watching the watcher. Demote the SELF row so it renders `SWEEP
    # UNSEEN` and reds the sweep. The real question (how long since the PREVIOUS completed sweep) is an
    # attribute of the SELF row, not of the daily gate, so we resolve it here off the same `/runs` API.
    for row in rows:
        if row["file"] == SELF and row.get("id"):
            last, last_sha = sweep_self_last_run(repo, gh, row["id"])
            if not last or _age_hours(last) > SWEEP_GATE_MAX_AGE_HOURS:
                row["role"] = "sweep_unseen"
                row["sweep_last_run"] = last or "never"
                row["sweep_last_sha"] = last_sha
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
