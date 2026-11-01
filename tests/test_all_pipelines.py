"""The umbrella sweep (issue #1102): one pipeline that exercises every dispatchable pipeline.

Every rule is exercised through the REAL module (scripts/all_pipelines.py) — classify, render_report,
dispatch_one, wait_for_dispatched_run, sweep — with the GitHub API standing in as a local stub `gh` binary
(the allowed external stand-in, like ci_requeue's `CI_REQUEUE_GH`), never with a mock of the product logic.
A disabled workflow MUST render `DISABLED (owner re-enable required)`, be excluded from ok/failed, and be
named in the excluded list: a green summary hiding dead pipelines is the exact failure mode this issue exists
to prevent (acceptance #5), and the test below locks it.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from scripts import all_pipelines as ap

REPO = Path(__file__).resolve().parent.parent


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    """A fixture repo tree with the given `.github/workflows/*.yml` files (name -> yaml text)."""
    root = tmp_path / "repo"
    (root / ".github" / "workflows").mkdir(parents=True)
    for name, text in files.items():
        (root / ".github" / "workflows" / name).write_text(text)
    return root


ACTIVE_DISPATCHABLE = "name: a-bot — does one thing\non:\n  workflow_dispatch:\n\njobs:\n  go:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n"
DISABLED_WF = "name: b-bot — does another thing\non:\n  workflow_dispatch:\n\njobs:\n  go:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n"
NO_DISPATCH = "name: c-bot — passive\non:\n  push:\n\njobs:\n  go:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n"


def make_stub(tmp_path: Path, workflows: list[dict], runs: list[dict],
              gate_last_run: str | None = None) -> Path:
    """A real stub `gh` binary (python, executable) serving the API the sweep calls.

    `workflows`: [{file, state, id}]; `runs`: a base list of workflow_dispatch runs to serve; the stub
    records every `workflow run` dispatch into a JSON state file so the test can assert what was dispatched.
    `gate_last_run`: when not None, an ISO-8601 created_at the stub serves for the security gate's
    `/actions/workflows/<id>/runs` call — the freshness half of the #1285 admission alarm.
    """
    stub = tmp_path / "gh-stub"
    state_file = tmp_path / "dispatched.json"
    state_file.write_text("[]")
    body = f'''#!/usr/bin/env python3
import sys, json, pathlib
WF = {json.dumps(workflows)}
RUNS = {json.dumps(runs)}
STATE = pathlib.Path({str(state_file)!r})
GATE_RUN = {json.dumps(gate_last_run)}
args = sys.argv[1:]
def out(doc):
    sys.stdout.write(json.dumps(doc))
    sys.stdout.write("\\n")
# gh api repos/X/actions/workflows  -> the workflows roster
if args[0] == "api" and args[1].endswith("/actions/workflows"):
    out([{{"path": ".github/workflows/"+w["file"], "state": w["state"], "id": w["id"]}} for w in WF])
    sys.exit(0)
# gh api repos/X/actions/workflows -> the workflows roster
if args[0] == "api" and args[1].endswith("/actions/workflows"):
    out([{{"path": ".github/workflows/"+w["file"], "state": w["state"], "id": w["id"]}} for w in WF])
    sys.exit(0)
# gh api repos/X/actions/workflows/<id>/runs -> prior runs OR the security gate's last run
# (newest-first, .workflow_runs[0].created_at). GATE_RUN, when set, is served for the security gate's
# workflow id so the staleness check has something real to read.
if args[0] == "api" and "/actions/workflows/" in args[1] and args[1].endswith("/runs"):
    gate_id = {{w["file"]: w["id"] for w in WF}}.get("security-scan.yml")
    if GATE_RUN is not None and args[1].endswith("/workflows/" + gate_id + "/runs"):
        out({{"workflow_runs": [{{"id": "1", "created_at": GATE_RUN}}]}})
    else:
        sys.stdout.write("")
    sys.exit(0)
# gh workflow run <file> --repo X --ref ref  -> record dispatch, exit 0 (NOT a verdict)
if args[0] == "workflow" and args[1] == "run":
    d = json.loads(STATE.read_text())
    d.append(args[2])
    STATE.write_text(json.dumps(d))
    out({{"message": "ok"}})
    sys.exit(0)
# gh api repos/X/actions/runs/<id> -> a completed verdict
import re
m = re.match(r"repos/.*/actions/runs/(\\d+)$", args[1])
if m:
    rid = m.group(1)
    ver = next((r for r in RUNS if str(r["id"]) == rid), RUNS[0] if RUNS else {{}})
    out({{"status": "completed", "conclusion": ver.get("conclusion", "success"), "completed_at": "2026-10-31T00:00:00Z"}})
    sys.exit(0)
# gh api repos/X/actions/runs -> the dispatched workflow_dispatch runs (gh's --jq emits the objects)
if args[0] == "api" and args[1].endswith("/actions/runs"):
    dispatched = json.loads(STATE.read_text())
    by_file = {{w["file"]: str(w["id"]) for w in WF}}
    served = []
    for f in dispatched:
        served.append({{"id": "5" + by_file[f], "workflow_id": by_file[f], "event": "workflow_dispatch"}})
    for s in served:
        out(s)
    sys.exit(0)
sys.exit(9)
'''
    stub.write_text(body)
    stub.chmod(0o755)
    return stub


def test_classify_marks_active_disabled_and_self(tmp_path):
    # Given a tree with one active dispatchable, one disabled, one passive, and the umbrella itself
    root = _tree(tmp_path, {
        "all-pipelines.yml": ACTIVE_DISPATCHABLE,
        "a-bot.yml": ACTIVE_DISPATCHABLE,
        "b-bot.yml": DISABLED_WF,
        "c-bot.yml": NO_DISPATCH,
    })
    states = {"a-bot.yml": {"state": "active", "active": True},
              "b-bot.yml": {"state": "disabled_manually", "active": False}}

    # When it is classified against the live states
    rows = ap.classify(root, states)

    # Then each role is right
    by_file = {r["file"]: r["role"] for r in rows}
    assert by_file["a-bot.yml"] == "dispatch"
    assert by_file["b-bot.yml"] == "disabled"
    assert by_file["c-bot.yml"] == "not_dispatchable"
    assert by_file["all-pipelines.yml"] == "self"


def test_a_disabled_workflow_is_reported_and_excluded(tmp_path):
    # Given a sweep where one workflow is disabled and one succeeds
    root = _tree(tmp_path, {"all-pipelines.yml": ACTIVE_DISPATCHABLE,
                            "a-bot.yml": ACTIVE_DISPATCHABLE,
                            "b-bot.yml": DISABLED_WF})
    states = {"a-bot.yml": {"state": "active", "active": True},
              "b-bot.yml": {"state": "disabled_manually", "active": False}}
    rows = ap.classify(root, states)
    concluded = {"a-bot.yml": {"run_id": "5", "status": "completed",
                               "conclusion": "success", "completed_at": "2026-10-31T00:00:00Z"}}

    # When the report is rendered
    report, code = ap.render_report(rows, concluded, "abc123")

    # Then the disabled workflow appears as DISABLED, is excluded from ok/failed, and is named in the excluded list
    assert "DISABLED (owner re-enable required)" in report
    assert report.count("DISABLED (owner re-enable required)") == 1
    assert "`b-bot.yml`" in report
    assert "Excluded — disabled (owner re-enable required):" in report
    assert "Summary: 1 ok · 0 failed · 1 disabled" in report
    assert code == 0


def test_a_disabled_workflow_treated_as_ok_is_a_failure(tmp_path):
    # The regression lock (acceptance #5): if a naive change counts a disabled workflow as "ok" (drops the
    # disabled list from the summary), the test must RED. Here we force `concluded` to pretend the disabled
    # workflow ran green — the report must still render it DISABLED and NOT count it as ok.
    root = _tree(tmp_path, {"all-pipelines.yml": ACTIVE_DISPATCHABLE,
                            "a-bot.yml": ACTIVE_DISPATCHABLE,
                            "b-bot.yml": DISABLED_WF})
    states = {"a-bot.yml": {"state": "active", "active": True},
              "b-bot.yml": {"state": "disabled_manually", "active": False}}
    rows = ap.classify(root, states)
    # deliberately hand the disabled workflow a "success" conclusion — as if someone treated it as green
    concluded = {"a-bot.yml": {"run_id": "5", "status": "completed", "conclusion": "success",
                               "completed_at": "2026-10-31T00:00:00Z"},
                 "b-bot.yml": {"run_id": "6", "status": "completed", "conclusion": "success",
                               "completed_at": "2026-10-31T00:00:00Z"}}

    report, _ = ap.render_report(rows, concluded, "abc123")

    # Then it still renders DISABLED (never ok) and the summary still counts 1 disabled, 1 ok (not 2 ok)
    assert "DISABLED (owner re-enable required)" in report
    assert "Summary: 1 ok · 0 failed · 1 disabled" in report


def test_every_disabled_workflow_is_reported(tmp_path):
    # Given several disabled and several active workflows
    root = _tree(tmp_path, {"all-pipelines.yml": ACTIVE_DISPATCHABLE,
                            "a1.yml": ACTIVE_DISPATCHABLE, "a2.yml": ACTIVE_DISPATCHABLE,
                            "d1.yml": DISABLED_WF, "d2.yml": DISABLED_WF, "d3.yml": DISABLED_WF})
    states = {"a1.yml": {"state": "active", "active": True},
              "a2.yml": {"state": "active", "active": True},
              "d1.yml": {"state": "disabled_manually", "active": False},
              "d2.yml": {"state": "disabled_manually", "active": False},
              "d3.yml": {"state": "disabled_manually", "active": False}}
    rows = ap.classify(root, states)
    concluded = {"a1.yml": {"run_id": "1", "status": "completed", "conclusion": "success",
                            "completed_at": "t"},
                 "a2.yml": {"run_id": "2", "status": "completed", "conclusion": "failure",
                            "completed_at": "t"}}

    # When the report is rendered
    report, code = ap.render_report(rows, concluded, "sha")

    # Then every disabled workflow is named, and failure isolation sets a non-zero exit at the END
    for d in ("d1.yml", "d2.yml", "d3.yml"):
        assert d in report
    assert "DISABLED (owner re-enable required)" in report
    assert report.count("DISABLED (owner re-enable required)") == 3
    assert "Summary: 1 ok · 1 failed · 3 disabled" in report
    assert code == 1


def test_failure_isolation_emits_full_table_and_fails_at_end(tmp_path):
    # Given a sweep where one dispatched run fails and another succeeds
    root = _tree(tmp_path, {"all-pipelines.yml": ACTIVE_DISPATCHABLE,
                            "a1.yml": ACTIVE_DISPATCHABLE, "a2.yml": ACTIVE_DISPATCHABLE})
    states = {"a1.yml": {"state": "active", "active": True},
              "a2.yml": {"state": "active", "active": True}}
    rows = ap.classify(root, states)
    concluded = {"a1.yml": {"run_id": "1", "status": "completed", "conclusion": "success",
                            "completed_at": "t"},
                 "a2.yml": {"run_id": "2", "status": "completed", "conclusion": "failure",
                            "completed_at": "t"}}

    report, code = ap.render_report(rows, concluded, "sha")

    # Then both rows are present (failure isolation: one red pipeline does not abort the output)
    assert "a1.yml" in report and "a2.yml" in report
    assert "completed/success" in report and "completed/failure" in report
    assert "Summary: 1 ok · 1 failed · 0 disabled" in report
    assert code == 1


def test_the_sweep_states_the_sha_it_swept(tmp_path):
    # Given a real tree at a known head sha
    root = _tree(tmp_path, {"all-pipelines.yml": ACTIVE_DISPATCHABLE,
                            "a-bot.yml": ACTIVE_DISPATCHABLE})
    states = {"a-bot.yml": {"state": "active", "active": True}}
    rows = ap.classify(root, states)
    concluded = {"a-bot.yml": {"run_id": "5", "status": "completed", "conclusion": "success",
                               "completed_at": "t"}}

    report, _ = ap.render_report(rows, concluded, "deadbeef")

    # Then the report carries the sha (a green is a fact about a tree, not a date)
    assert "deadbeef" in report
    assert "# all-pipelines sweep @ deadbeef" in report


def test_classify_treats_an_unknown_file_as_active(tmp_path):
    # A brand-new workflow the API is a step behind must NOT be silently skipped as disabled
    root = _tree(tmp_path, {"all-pipelines.yml": ACTIVE_DISPATCHABLE,
                            "brand-new.yml": ACTIVE_DISPATCHABLE})
    # note: brand-new.yml is absent from `states`
    rows = ap.classify(root, {})
    by_file = {r["file"]: r["role"] for r in rows}
    assert by_file["brand-new.yml"] == "dispatch"


def test_the_umbrella_dispatches_every_dispatchable_except_itself_and_awaits(tmp_path):
    # Given a live-ish repo facing a stub gh with two active dispatchable + the umbrella + one disabled
    workflows = [
        {"file": "all-pipelines.yml", "state": "active", "id": "10"},
        {"file": "arms.yml", "state": "active", "id": "20"},
        {"file": "holds.yml", "state": "active", "id": "30"},
        {"file": "security-scan.yml", "state": "disabled_manually", "id": "40"},
        {"file": "other-bot.yml", "state": "disabled_manually", "id": "50"},
    ]
    stub = make_stub(tmp_path, workflows, runs=[])
    root = tmp_path / "wf"
    (root / ".github" / "workflows").mkdir(parents=True)
    for f in ("all-pipelines.yml", "arms.yml", "holds.yml", "security-scan.yml", "other-bot.yml"):
        (root / ".github" / "workflows" / f).write_text(ACTIVE_DISPATCHABLE)

    # When the sweep runs against the stub gh (repo arg is arbitrary; the stub ignores it)
    report, code = ap.sweep("owner/repo", "main", gh=str(stub), timeout=30, root=root)

    # Then the umbrella itself was NOT dispatched (no recursion), both active dispatchable were, the
    # ordinary disabled workflow is reported+excluded (exit contribution only from real failures) —
    # and the SECURITY admission gate, being disabled_manually, is NOT a benign DISABLED row: it is an
    # ADMISSION GATE DOWN that FAILS the sweep (issue #1285).
    dispatched = json.loads((tmp_path / "dispatched.json").read_text())
    assert "all-pipelines.yml" not in dispatched
    assert "arms.yml" in dispatched
    assert "holds.yml" in dispatched
    assert "security-scan.yml" not in dispatched
    assert "other-bot.yml" not in dispatched
    assert "DISABLED (owner re-enable required)" in report
    assert "`other-bot.yml`" in report
    assert "ADMISSION GATE DOWN (issue #1285" in report
    assert "`security-scan.yml`" in report
    assert "1 ADMISSION GATE DOWN" in report
    assert "Summary: 2 ok · 0 failed · 1 disabled" in report
    assert code == 1  # the admission gate being down is a red industrial alarm, not exit 0


def test_real_tree_has_all_pipelines_yml_and_sweep_render_exercises_it():
    # The umbrella must exist in the real tree and its own file must be present in the sweep's roster so the
    # `self` exclusion is exercised against reality, not just fixtures.
    assert (REPO / ap.WORKFLOWS / ap.SELF).exists()
    assert "all-pipelines.yml" in ap.workflow_files(REPO)
    # The real tree must classify (no crash) — states come from a live call, so we only assert structure.
    rows = ap.classify(REPO, {})
    by_file = {r["file"]: r["role"] for r in rows}
    assert by_file[ap.SELF] == "self"


def test_a_disabled_security_gate_reds_the_sweep(tmp_path):
    # Issue #1285, the primary case: `security-scan.yml` `disabled_manually` must be an ADMISSION GATE
    # DOWN that fails the sweep — NOT a benign DISABLED row the board reads as "scanned clean".
    root = _tree(tmp_path, {"all-pipelines.yml": ACTIVE_DISPATCHABLE,
                            "a-bot.yml": ACTIVE_DISPATCHABLE,
                            "security-scan.yml": DISABLED_WF})
    states = {"a-bot.yml": {"state": "active", "active": True},
              "security-scan.yml": {"state": "disabled_manually", "active": False}}
    rows = ap.classify(root, states)
    by_file = {r["file"]: r["role"] for r in rows}
    assert by_file["security-scan.yml"] == "admission_down"
    concluded = {"a-bot.yml": {"run_id": "5", "status": "completed", "conclusion": "success",
                               "completed_at": "t"}}

    report, code = ap.render_report(rows, concluded, "abc123")

    assert "ADMISSION GATE DOWN (issue #1285" in report
    assert "`security-scan.yml`" in report
    assert "1 ADMISSION GATE DOWN" in report
    assert code == 1


def test_an_ordinary_disabled_workflow_is_still_benign(tmp_path):
    # The admission alarm is SECURITY-GATE-SPECIFIC: every other disabled workflow stays a benign
    # DISABLED row and contributes nothing to the exit code (issue #1102 invariants unchanged).
    root = _tree(tmp_path, {"all-pipelines.yml": ACTIVE_DISPATCHABLE,
                            "a-bot.yml": ACTIVE_DISPATCHABLE,
                            "b-bot.yml": DISABLED_WF})
    states = {"a-bot.yml": {"state": "active", "active": True},
              "b-bot.yml": {"state": "disabled_manually", "active": False}}
    rows = ap.classify(root, states)
    by_file = {r["file"]: r["role"] for r in rows}
    assert by_file["b-bot.yml"] == "disabled"
    assert "security-scan.yml" not in by_file
    concluded = {"a-bot.yml": {"run_id": "5", "status": "completed", "conclusion": "success",
                               "completed_at": "t"}}
    report, code = ap.render_report(rows, concluded, "abc123")
    assert "DISABLED (owner re-enable required)" in report
    assert "0 ADMISSION GATE DOWN" in report
    assert code == 0


def test_an_active_gate_with_no_recent_run_is_stale_and_reds(tmp_path):
    # Issue #1285 freshness half: a gate that is NOT disabled_manually but whose schedule silently
    # stopped firing (a broken cron re-fires nothing and never flips state) is as unsafe as a disabled
    # one — the sweep must demote it to ADMISSION GATE STALE and fail.
    from datetime import datetime, timezone, timedelta
    stale = (datetime.now(timezone.utc) - timedelta(hours=100)).isoformat()
    workflows = [
        {"file": "all-pipelines.yml", "state": "active", "id": "10"},
        {"file": "a-bot.yml", "state": "active", "id": "20"},
        {"file": "security-scan.yml", "state": "active", "id": "40"},
    ]
    stub = make_stub(tmp_path, workflows, runs=[], gate_last_run=stale)
    root = tmp_path / "wf"
    (root / ".github" / "workflows").mkdir(parents=True)
    for f in ("all-pipelines.yml", "a-bot.yml", "security-scan.yml"):
        (root / ".github" / "workflows" / f).write_text(ACTIVE_DISPATCHABLE)

    report, code = ap.sweep("owner/repo", "main", gh=str(stub), timeout=30, root=root)

    dispatched = json.loads((tmp_path / "dispatched.json").read_text())
    assert "security-scan.yml" not in dispatched     # demoted: not dispatched as a healthy gate
    assert "ADMISSION GATE STALE" in report
    assert "`security-scan.yml`" in report
    assert "1 ADMISSION GATE DOWN" in report
    assert code == 1


def test_an_active_gate_with_a_recent_run_is_swept_normally(tmp_path):
    # A healthy gate with a fresh run inside the daily cadence is dispatched like any other active
    # dispatchable workflow and contributes nothing to the admission alarm.
    from datetime import datetime, timezone, timedelta
    fresh = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    workflows = [
        {"file": "all-pipelines.yml", "state": "active", "id": "10"},
        {"file": "a-bot.yml", "state": "active", "id": "20"},
        {"file": "security-scan.yml", "state": "active", "id": "40"},
    ]
    stub = make_stub(tmp_path, workflows, runs=[], gate_last_run=fresh)
    root = tmp_path / "wf"
    (root / ".github" / "workflows").mkdir(parents=True)
    for f in ("all-pipelines.yml", "a-bot.yml", "security-scan.yml"):
        (root / ".github" / "workflows" / f).write_text(ACTIVE_DISPATCHABLE)

    report, code = ap.sweep("owner/repo", "main", gh=str(stub), timeout=30, root=root)

    dispatched = json.loads((tmp_path / "dispatched.json").read_text())
    assert "security-scan.yml" in dispatched         # healthy gate is swept like any other
    assert "0 ADMISSION GATE DOWN" in report
    assert code == 0
