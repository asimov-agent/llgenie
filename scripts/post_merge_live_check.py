#!/usr/bin/env python3
"""Post-merge live verification read (issue #2900).

Every landing onto `main` ends with this read: the newest `main` run of each live battery
(`registry-liveness.yml`, `ci-hf-live.yml`) must be `success`, and the committed trend matrix
must still match the vendored trending data (`trend_list_matrix.py --check`, the same seam as
`make -s check-trend-list-matrix`). A red battery or a fingerprint mismatch exits non-zero and
names the trend-refresh action (the #2900/#2901 rule: a `ci-hf-live` red whose diff is
fixture-vs-live trend drift opens or links one trend-refresh issue naming the disagreeing
cells, in the same breath as the landing record); re-running the battery away is forbidden.

Read discipline: `gh` owns the API read (the same seam `queued_run_alarm` uses); the fingerprint
read shells out to the battery's own script, not a second matrix implementation. A stream that
cannot be read exits 2 — never a silent zero. A battery with no completed main run is itself red
("never ran on main"). Only names, run ids, event names and conclusions are printed — never raw
payloads, never token-shaped values (`GITHUB_TOKEN` reaches `gh` through the job environment and
this module never forwards or prints it).

Usage: post_merge_live_check.py [--repo OWNER/REPO] [--workflow NAME ...] [--json]
Exit: 0 = every battery green on main + fingerprint matches; 1 = a battery is red on main or the
fingerprint mismatched; 2 = the read failed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO = "asimov-agent/llgenie"

#: The batteries a landing must read (issue #2900): the registry/engine trend liveness battery
#: and the live trending battery. A new battery is added here once, with its issue.
BATTERIES = ("registry-liveness.yml", "ci-hf-live.yml")


def _gh(args: list[str]) -> str:
    """`gh` is the API seam (the queued_run_alarm pattern): GET with the query embedded in the
    URL (a `-f` on a GET endpoint makes gh POST, and POSTing the runs-list endpoint 404s),
    status + JSON only, never a raw payload."""
    r = subprocess.run(  # proc-allow: the landing read shells out to gh, the repo's API seam (tracked remainder for #797)
        ["gh", *args], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {r.stderr.strip()[:160]}")
    return r.stdout


def _matrix_check() -> tuple[bool, str]:
    """The fingerprint read: the battery's own hermetic seam (`trend_list_matrix.py --check`)."""
    r = subprocess.run(  # proc-allow: the fingerprint read reuses scripts/trend_list_matrix.py rather than re-implementing matrix()
        [sys.executable, str(REPO_ROOT / "scripts" / "trend_list_matrix.py"), "--check"],
        capture_output=True, text=True, timeout=300)
    line = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
    return r.returncode == 0, (line[0][:200] if line else "")


def newest_main_run(repo: str, workflow: str) -> dict | None:
    """The newest completed run of `workflow` headed at `main` — a landing read, not a PR read."""
    rows = json.loads(_gh(["api", "-X", "GET",
                           f"/repos/{repo}/actions/workflows/{workflow}/runs"
                           "?branch=main&per_page=10"]))
    for run in rows.get("workflow_runs", []):
        if run.get("head_branch") == "main" and run.get("status") == "completed":
            # the LIST endpoint names its fields `id`/`event` (only the single-run GET has run_id)
            return {"run_id": run.get("id"), "event": run.get("event"),
                    "conclusion": run.get("conclusion")}
    return None


def battery_verdict(repo: str, workflow: str, *, run_reader=None) -> dict:
    run = (run_reader or newest_main_run)(repo, workflow)
    if run is None:
        return {"workflow": workflow, "run_id": None, "event": None, "conclusion": None,
                "green": False, "note": "battery never completed a run on main"}
    return {"workflow": workflow, **run, "green": run["conclusion"] == "success", "note": ""}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--workflow", action="append", choices=list(BATTERIES),
                    help="restrict the read to named batteries (default: all)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    batteries = args.workflow or list(BATTERIES)
    try:
        verdicts = [battery_verdict(args.repo, wf) for wf in batteries]
    except Exception as exc:  # noqa: BLE001  (a stream that cannot be read is exit 2, never silent zero)
        print(f"post-merge-live-check: CANNOT READ ({exc})", file=sys.stderr)
        return 2

    ok, note = _matrix_check()
    fp = {"fingerprint": "check-trend-list-matrix", "green": ok, "note": note}

    if args.json:
        print(json.dumps({"repo": args.repo, "batteries": verdicts, "fingerprint": fp}))
    else:
        for v in verdicts:
            print(f"post-merge-live-check: {v['workflow']} run={v['run_id']} event={v['event']} "
                  f"conclusion={v['conclusion']} green={int(v['green'])}"
                  + (f" note={v['note']}" if v["note"] else ""))
        print(f"post-merge-live-check: {fp['fingerprint']} green={int(fp['green'])}"
              + (f" note={fp['note']}" if fp["note"] else ""))

    if all(v["green"] for v in verdicts) and fp["green"]:
        print("post-merge-live-check: OK — batteries green on main, trend matrix matches the "
              "vendored trending (the live trending truth is the ci-hf-live verdict above)")
        return 0
    print("post-merge-live-check: NOT DONE — a battery is red on main or the trend matrix "
          "drifted; open (or link) one trend-refresh issue naming the disagreeing cells and "
          "land nothing on main over a red battery (issue #2900; the staleness home is #2901)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
