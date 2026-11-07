"""A cancelled fan-out is not a legitimate skip (#1111).

The defect this suite pins, measured 2026-10-30 on run **41134761297** (`CI`, head `0bd5ac6e`,
conclusion `cancelled`):

    guard success · ci-images cancelled · scanner-images cancelled · linux skipped
    => success=3, failed=0, other=5, pending=0          (no `linux / unit` row existed at all)

The same class of change at `d92ee6a3` (run **41126873965**) had the full set with
`linux / unit failure`: one head proved the change was wrong, and the next head — after a push
cancelled the fan-out — proved nothing while every summary line read "0 failures".

So the answer needs a DECISION, not another conclusion count: `scripts/ci_scope.py::decision()` is the
artifact `ci.yml`'s `guard` job publishes, `verify()` is the accounting, and `scripts/ci_verdict.py` is
the consumer that posts the answer as a `ci-verdict` check-run. Every case below is one of those four
answers: selected-and-passed, selected-but-missing (red), not-selected-and-skipped (green), and no
decision at all (`none`, red).

The negative control is `test_a_cancelled_fan_out_with_no_decision_is_never_green`: let `verify()`
treat a missing decision as a pass — the old behaviour in one line — and it reds.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

import scripts.ci_scope as cs
import scripts.ci_verdict as cv

REPO = Path(__file__).resolve().parents[1]

WF = REPO / ".github" / "workflows"

#: Run 41134761297 — the cancelled fan-out, exactly as the API returned it.
CANCELLED_FANOUT = [
    {"name": "guard", "status": "completed", "conclusion": "success"},
    {"name": "ci-images", "status": "completed", "conclusion": "cancelled"},
    {"name": "scanner-images", "status": "completed", "conclusion": "cancelled"},
    {"name": "linux", "status": "completed", "conclusion": "skipped"},
]

#: Run 41126873965 — the same class of change, where the unit gate actually ran and failed.
RED_RUN = [
    {"name": "guard", "status": "completed", "conclusion": "success"},
    {"name": "ci-images", "status": "completed", "conclusion": "success"},
    {"name": "scanner-images", "status": "completed", "conclusion": "success"},
    {"name": "linux / cpu-health", "status": "completed", "conclusion": "success"},
    {"name": "linux / unit", "status": "completed", "conclusion": "failure"},
    {"name": "linux / top-tier (none)", "status": "completed", "conclusion": "success"},
    {"name": "linux / agents-read", "status": "completed", "conclusion": "success"},
    {"name": "linux / openspec", "status": "completed", "conclusion": "success"},
    {"name": "linux / install", "status": "completed", "conclusion": "success"},
    {"name": "linux / lint", "status": "completed", "conclusion": "success"},
]

#: A docs-only diff (`ci.yml` is not even started for it) — the legitimate skip, and only those.
DOCS_DECISION_PATH = ["docs/ARCHITECTURE.md", "CHANGES.md"]

#: A WILDCARD path: it can change what any gate proves, so the classifier selects every class — the
#: full-matrix decision a code change gets.
FULL_MATRIX_PATH = ["Makefile"]


def decision_for(paths: list[str]) -> dict:
    """The real decision the classifier publishes for a diff — never a hand-written job table."""
    classes, _unmatched, wide = cs.classify(paths)
    return cs.decision(classes, cs.select(classes), paths, wide)


def summary(result: dict) -> str:
    return next(line for line in result["lines"] if "summary:" in line)


# ---- 1. no decision at all: `none`, never a pass -------------------------------------

def test_a_cancelled_fan_out_with_no_decision_is_never_green():
    """The bug in one case: nothing decided, a job skipped, and the summary must NOT read clean."""

    # Given the measured cancelled fan-out and NO decision artifact (the run never published one)
    result = cs.verify(None, CANCELLED_FANOUT)

    # When  the verdict is computed
    verdict, counts = result["verdict"], result["counts"]

    # Then  it is `none` — not green — and the three rows that are not a verdict are unaccounted
    assert verdict == cs.NONE, result["lines"]
    assert counts["success"] == 1 and counts["failure"] == 0
    assert counts["no_verdict"] == 3, counts          # ci-images, scanner-images, linux (skipped)

    # And  the summary says so in a sentence a reader cannot mistake for a pass
    line = summary(result)
    assert "verdict=none" in line and "failure=0" in line, line
    assert any("0 failures is not a verdict" in l for l in result["lines"]), result["lines"]

    # And  the check-run it would post is a FAILURE, never a success
    payload = cs.check_run_payload(verdict, "0bd5ac6e", result["lines"])
    assert payload["conclusion"] == "failure", payload


# ---- 2. a decision exists and the selected job never reported: red -------------------

def test_a_selected_job_that_never_reported_reds_the_verdict():
    # Given a decision that selects the whole matrix and the cancelled fan-out's four rows
    decision = decision_for(FULL_MATRIX_PATH)

    # When  the run is held to it
    result = cs.verify(decision, CANCELLED_FANOUT)

    # Then  `linux / unit` is named as ABSENT and the verdict is `none`
    assert result["verdict"] == cs.NONE, result["lines"]
    assert any("linux/unit ABSENT" in line for line in result["lines"]), result["lines"]
    assert result["counts"]["failure"] == 0
    assert result["counts"]["no_verdict"] >= 1


def test_a_cancelled_row_the_decision_selected_is_unaccounted_not_skipped_by_decision():
    # Given the same decision, and the two image jobs reported CANCELLED rather than skipped
    result = cs.verify(decision_for(FULL_MATRIX_PATH), CANCELLED_FANOUT)

    # Then  neither `cancelled` image job is ever counted as a legitimate skip
    assert result["counts"]["skipped_by_decision"] == 0, result["counts"]
    assert any("ci-images cancelled" in line and "selected it" in line for line in result["lines"])


# ---- 3. a skip the DECISION made is green, and it is named --------------------------

#: A `tests/**` change: `unit` and `lint` are selected, the scanner images, `install`, `agents-read`,
#: `openspec` and `cpu-health` are not. This is what a legitimate skip looks like in a CI run — the
#: real docs-only diff does not start `ci.yml` at all, so it never reaches a verdict.
TESTS_PATH = ["tests/test_ci_verdict.py"]

#: Run rows for a `tests/**` diff, exactly as `ci.yml` reports them (called-workflow and placeholder
#: names included).
TESTS_RUN = [
    {"name": "guard", "status": "completed", "conclusion": "success"},
    {"name": "ci-images", "status": "completed", "conclusion": "success"},
    {"name": "scanner-images", "status": "completed", "conclusion": "skipped"},
    {"name": "linux", "status": "completed", "conclusion": "success"},
    {"name": "linux / lint", "status": "completed", "conclusion": "success"},
    {"name": "linux / unit", "status": "completed", "conclusion": "success"},
    {"name": "linux / top-tier (none)", "status": "completed", "conclusion": "success"},
]


def test_a_skip_the_decision_made_is_green_and_counted():
    """The other half: "not needed" must stay legal, or the gate becomes a full matrix for every diff."""

    # Given a `tests/**` decision (unit + lint selected, the rest deliberately not needed)
    decision = decision_for(TESTS_PATH)
    assert decision["jobs"]["linux/unit"]["run"] is True
    assert decision["jobs"]["scanner-images"]["run"] is False

    # When  the run is held to that decision
    result = cs.verify(decision, TESTS_RUN)

    # Then  it is green, and every skip is counted as the decision's, not as a non-verdict
    assert result["verdict"] == cs.GREEN, result["lines"]
    assert result["counts"]["skipped_by_decision"] == 5, result["counts"]   # scanner + 4 absent
    assert result["counts"]["no_verdict"] == 0 and result["counts"]["failure"] == 0
    assert "0 failures is not a verdict" not in " ".join(result["lines"])


def test_a_skip_the_decision_made_and_a_skip_without_a_decision_are_distinguishable():
    """The same job rows, two verdicts — the whole point of the issue."""
    jobs = [{"name": "guard", "status": "completed", "conclusion": "success"},
            {"name": "linux", "status": "completed", "conclusion": "skipped"}]

    # Given identical rows read against a decision that skipped the matrix, and against no decision
    by_decision = cs.verify(decision_for(DOCS_DECISION_PATH), jobs)
    no_decision = cs.verify(None, jobs)

    # Then  the skipped `linux` is a decision in the first and a non-verdict in the second... except
    # that the docs decision still SELECTS `lint` and `openspec`, which the skipped run never reported,
    # so that case is red on its own merits — and the summaries can never be the same string.
    assert by_decision["verdict"] == cs.NONE, by_decision["lines"]
    assert any("linux/openspec ABSENT" in line for line in by_decision["lines"]), by_decision["lines"]
    assert no_decision["verdict"] == cs.NONE
    assert "NO DECISION" in " ".join(no_decision["lines"])
    assert "NO DECISION" not in " ".join(by_decision["lines"])
    assert summary(by_decision) != summary(no_decision)


# ---- 4. a real failure is still a failure (no false green, no swallowed red) --------

def test_the_measured_red_run_stays_red_and_names_the_unit_gate():
    # Given run 41126873965, whose `linux / unit` failed
    result = cs.verify(decision_for(FULL_MATRIX_PATH), RED_RUN)

    # Then  the verdict is red and the failing gate is named
    assert result["verdict"] == cs.RED, result["lines"]
    assert result["counts"]["failure"] == 1
    assert any("linux/unit FAILED" in line for line in result["lines"]), result["lines"]


def test_a_job_with_no_conclusion_is_pending_and_never_a_pass():
    # Given a row that completed with no conclusion (a job that never started)
    jobs = [{"name": "guard", "status": "completed", "conclusion": "success"},
            {"name": "linux / unit", "status": "queued", "conclusion": ""}]

    # When  it is verified against a decision that selected the matrix
    result = cs.verify(decision_for(FULL_MATRIX_PATH), jobs)

    # Then  it is a non-verdict, counted as pending, and the verdict is not green
    assert result["verdict"] == cs.NONE, result["lines"]
    assert result["counts"]["pending"] == 1, result["counts"]


# ---- 5. the payload: failure for `none`, neutral for a superseded head --------------

def test_the_check_run_payload_maps_the_verdict_and_never_calls_none_a_success():
    assert cs.check_run_payload(cs.GREEN, "abc", ["x"])["conclusion"] == "success"
    assert cs.check_run_payload(cs.RED, "abc", ["x"])["conclusion"] == "failure"
    assert cs.check_run_payload(cs.NONE, "abc", ["x"])["conclusion"] == "failure"

    # And the SUPERSEDED override is neutral — a head a later run owns is owed nothing, and still
    # never reads as a pass.
    payload = cs.check_run_payload(cs.NONE, "abc", ["x"], conclusion="neutral", run_label="run 1")
    assert payload["conclusion"] == "neutral" and payload["name"] == "ci-verdict"
    assert payload["status"] == "completed" and payload["head_sha"] == "abc"
    assert "run 1" in payload["output"]["title"]


def test_the_verdict_header_attributes_the_judged_run_event_and_pr_not_the_wrapper():
    """The posted verdict names the run it JUDGED (event + PR + branch), so a PR-run red never reads
    as a merged-main-tip red (#1862). The wrapper's own head is the default branch; the attribution
    keeps the judged run's identity in the summary a board quotes."""
    run = {"id": 42216017972, "name": "CI", "head_sha": "bcd3fea614a76a6d748145292aadf39a56e486e6",
           "conclusion": "failure", "event": "pull_request",
           "pull_requests": [{"number": 1850}], "head_branch": "agent/issue-1849-pr-mc-log-read"}
    result = {"lines": ["[ci-scope] summary: verdict=red"], "verdict": cs.RED}
    lines = cv.verdict_lines(result, run, None)
    header = lines[0]
    assert "event=pull_request" in header, header
    assert "pr=1850" in header, header
    assert "branch=agent/issue-1849-pr-mc-log-read" in header, header
    assert "head=bcd3fea" in header, header
    # and a push-to-main run attributes as a push, never inventing a PR
    push = {"id": 42215438505, "name": "CI", "head_sha": "cdcbac4a2e3a16551f6ee88d5ed339c212ee6c62",
            "conclusion": "success", "event": "push", "pull_requests": [], "head_branch": "main"}
    plines = cv.verdict_lines({"lines": ["ok"], "verdict": cs.GREEN}, push, None)
    assert "event=push" in plines[0] and "pr=" not in plines[0], plines[0]
    assert "branch=main" in plines[0], plines[0]


# ---- 6. the classifier's decision round-trips through the artifact -------------------

def test_the_decision_artifact_round_trips_and_the_run_is_green(tmp_path):
    # Given `make ci-scope DECISION=…` on a tests diff, written by the CLI
    out = tmp_path / "ci-scope-decision.json"
    rc = cs.main(["--paths", "tests/test_ci_verdict.py", "--decision-out", str(out),
                  "--github-output", str(tmp_path / "gh-output")])

    # When  the published decision is read back by the verdict
    assert rc == 0, rc
    decision = json.loads(out.read_text(encoding="utf-8"))
    jobs = [{"name": "guard", "status": "completed", "conclusion": "success"},
            {"name": "ci-images", "status": "completed", "conclusion": "success"},
            {"name": "scanner-images", "status": "completed", "conclusion": "skipped"},
            {"name": "linux", "status": "completed", "conclusion": "success"},
            {"name": "linux / unit", "status": "completed", "conclusion": "success"},
            {"name": "linux / install", "status": "completed", "conclusion": "success"},
            {"name": "linux / agents-read", "status": "completed", "conclusion": "success"},
            {"name": "linux / openspec", "status": "completed", "conclusion": "success"},
            {"name": "linux / lint", "status": "completed", "conclusion": "success"},
            {"name": "linux / cpu-health", "status": "completed", "conclusion": "success"},
            {"name": "linux / top-tier (none)", "status": "completed", "conclusion": "success"}]

    # Then  the schema is the version the verdict reads, and the run is green
    assert decision["schema"] == cs.DECISION_SCHEMA
    assert decision["jobs"]["linux/unit"]["run"] is True
    assert decision["jobs"]["scanner-images"]["run"] is False
    result = cs.verify(decision, jobs)
    assert result["verdict"] == cs.GREEN, result["lines"]
    assert result["counts"]["skipped_by_decision"] == 1


def test_a_matrix_row_name_is_folded_to_its_identity():
    # Given the names GitHub prints for a called workflow and a placeholder row
    # Then  both fold to the classifier's spelling, so a row cannot be "absent" for a cosmetic reason
    assert cs.normalise_job_name("linux / unit") == "linux/unit"
    assert cs.normalise_job_name("linux / top-tier (none)") == "linux/top-tier"
    assert cs.normalise_job_name("linux") == "linux"
    assert cs.normalise_job_name("guard") == "guard"


# ---- 7. the CLI: exit codes, and the superseded head -------------------------------

def _cli(tmp_path, jobs, decision=None) -> tuple[int, Path]:
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps({"jobs": jobs, "total_count": len(jobs)}), encoding="utf-8")
    checks = tmp_path / "check-run.json"
    argv = ["--jobs", str(jobs_file), "--head-sha", "0bd5ac6e", "--check-run-out", str(checks)]
    if decision is not None:
        decision_file = tmp_path / "decision.json"
        decision_file.write_text(json.dumps(decision), encoding="utf-8")
        argv += ["--decision", str(decision_file)]
    return cv.main(argv), checks


def test_the_verdict_does_not_judge_its_own_posted_check_run(tmp_path, capsys):
    """A green run whose job list contains its own `ci-verdict` check-run judges green (#1882).

    `ci-verdict.yml`'s `judge` posts a check-run named `ci-verdict` to the head, and GitHub
    attributes that posted check-run back into the judged run's job list (measured on run
    42275871131 @ cf88d285: an 11th job `ci-verdict` with `workflow_name: "CI"`). Before the fix
    `verify()` saw a `ci-verdict` job not in the 10-job decision table, concluded `failure`, and
    red a run whose real jobs were all green — a feedback loop. The verdict must not judge itself.
    """

    # Given a full-matrix decision and the 10 real jobs all green PLUS the run's own ci-verdict row
    decision = decision_for(FULL_MATRIX_PATH)
    jobs = [{"name": "guard", "status": "completed", "conclusion": "success"},
            {"name": "ci-images", "status": "completed", "conclusion": "success"},
            {"name": "scanner-images", "status": "completed", "conclusion": "success"},
            {"name": "linux/lint", "status": "completed", "conclusion": "success"},
            {"name": "linux/unit", "status": "completed", "conclusion": "success"},
            {"name": "linux/install", "status": "completed", "conclusion": "success"},
            {"name": "linux/agents-read", "status": "completed", "conclusion": "success"},
            {"name": "linux/openspec", "status": "completed", "conclusion": "success"},
            {"name": "linux/top-tier", "status": "completed", "conclusion": "success"},
            {"name": "linux/cpu-health", "status": "completed", "conclusion": "success"},
            {"name": "ci-verdict", "status": "completed", "conclusion": "failure"}]

    # When  the verdict runs against those jobs
    rc, checks = _cli(tmp_path, jobs, decision=decision)
    out = capsys.readouterr().out

    # Then  it exits 0 and posts success — the ci-verdict row is not counted as a failure
    assert rc == 0, out
    payload = json.loads(checks.read_text(encoding="utf-8"))
    assert payload["conclusion"] == "success"
    assert "verdict=green" in payload["output"]["summary"], payload["output"]["summary"]
    assert "ci-verdict FAILED" not in payload["output"]["summary"], payload["output"]["summary"]


def test_the_cli_exits_one_and_writes_a_failure_check_run_for_a_cancelled_run(tmp_path, capsys):
    # Given the measured cancelled fan-out and no decision
    rc, checks = _cli(tmp_path, CANCELLED_FANOUT)

    # When  the verdict CLI runs
    out = capsys.readouterr().out

    # Then  it exits 1 (a red verdict, the exit code `make ci-verdict` turns into a red job)
    assert rc == 1, out
    assert "verdict=none" in out and "0 failures is not a verdict" in out

    # And  the payload it wrote is a failure on the head
    payload = json.loads(checks.read_text(encoding="utf-8"))
    assert payload["conclusion"] == "failure" and payload["head_sha"] == "0bd5ac6e"


def test_the_cli_exits_zero_and_writes_a_success_check_run_for_a_decided_skip(tmp_path, capsys):
    # Given a `tests/**` decision and a run whose fan-out was skipped by it
    # When  the verdict CLI runs
    rc, checks = _cli(tmp_path, TESTS_RUN, decision=decision_for(TESTS_PATH))

    # Then  it exits 0 and the payload is a success that NAMES the skip
    assert rc == 0, capsys.readouterr().out
    payload = json.loads(checks.read_text(encoding="utf-8"))
    assert payload["conclusion"] == "success"
    assert "skipped-by-decision=5" in payload["output"]["summary"], payload["output"]["summary"]


def test_a_mid_upload_job_row_is_refused_not_a_verdict(tmp_path, capsys):
    """The #2010/#1969 race: a `workflow_run` `completed` event can fire while the run's own
    `linux / unit` is still mid-upload — the jobs listing carries `in_progress` with no
    conclusion. Counting that row as `pending` posted a false `no_verdict`. The settle gate
    must REFUSE (exit 2, no check-run), never reach a verdict from a snapshot the run has not
    finished writing."""
    # Given a decision that selects the whole matrix, and a jobs listing where linux/unit has
    # NOT yet reported completed (still in_progress, mid-upload — the measured race shape)
    jobs = [{"name": "guard", "status": "completed", "conclusion": "success"},
            {"name": "ci-images", "status": "completed", "conclusion": "success"},
            {"name": "scanner-images", "status": "completed", "conclusion": "success"},
            {"name": "linux / unit", "status": "in_progress", "conclusion": None}]

    # When  the verdict CLI runs against that unsettled snapshot
    rc, checks = _cli(tmp_path, jobs, decision=decision_for(FULL_MATRIX_PATH))
    err = capsys.readouterr().err

    # Then  it exits 2 — never 0 and never a red verdict — and writes NO check-run
    assert rc == 2, err
    assert "not settled" in err and "linux / unit" in err, err
    assert not checks.exists(), "a mid-upload run must not produce a posted verdict"


def test_a_completed_row_without_a_conclusion_is_refused_not_a_red_verdict(tmp_path, capsys):
    """The #2046/#2035 half of the mid-upload race: GitHub writes a finishing run's `status`
    before its `conclusion`, so a row that reports `status: completed` with a still-empty
    `conclusion` is a run still settling through the conclusion field. The settle gate must
    REFUSE it (exit 2, no check-run) — never count it `pending` and reach a red verdict from a
    snapshot the run has not finished writing (the pre-fix behaviour was exit 1 + a posted
    `conclusion=failure`, measured against this tree before the conclusion check existed)."""
    # Given a decided run where linux/unit reports `completed` but its conclusion has not landed yet
    jobs = [{"name": "guard", "status": "completed", "conclusion": "success"},
            {"name": "ci-images", "status": "completed", "conclusion": "success"},
            {"name": "scanner-images", "status": "completed", "conclusion": "success"},
            {"name": "linux / unit", "status": "completed", "conclusion": None}]

    # When  the verdict CLI runs against that still-settling snapshot
    rc, checks = _cli(tmp_path, jobs, decision=decision_for(FULL_MATRIX_PATH))
    err = capsys.readouterr().err

    # Then  it exits 2 — never 0 and never a red verdict — and writes NO check-run
    assert rc == 2, err
    assert "not settled" in err and "linux / unit" in err, err
    assert not checks.exists(), "a completed-but-conclusion-less row must not produce a posted verdict"


def test_a_mid_upload_row_is_an_error_never_a_pass_through_the_api(tmp_path, monkeypatch, capsys):
    """The same gate on the run-id (API) path: the stub answers run_info/branch reads while a
    --jobs file carries the in_progress row — the judge exits 2 with its own FAILED line, and the
    workflow surfaces it rather than a verdict on the head."""
    jobs = [{"name": "guard", "status": "completed", "conclusion": "success"},
            {"name": "linux / unit", "status": "in_progress", "conclusion": None}]
    jobs_file = tmp_path / "unsettled.json"
    jobs_file.write_text(json.dumps({"jobs": jobs, "total_count": len(jobs)}), encoding="utf-8")

    monkeypatch.setenv("CI_VERDICT_GH", _stub_gh(tmp_path, artifact=True, later_run=False))
    rc = cv.main(["--repo", "o/r", "--run-id", "41134761297",
                  "--jobs", str(jobs_file), "--head-sha", "0bd5ac6e"])
    err = capsys.readouterr().err
    assert rc == cv.EXIT_ERROR, err
    assert "not settled" in err and "linux / unit" in err, err


def test_a_fully_settled_red_run_still_exits_one_through_the_settle_gate(tmp_path, capsys):
    """The settle gate never weakens a real red: every job `completed`, the unit failed — verdict
    is still red (exit 1), exactly as before the gate existed."""
    rc, checks = _cli(tmp_path, RED_RUN, decision=decision_for(FULL_MATRIX_PATH))
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "linux/unit FAILED" in out, out
    payload = json.loads(checks.read_text(encoding="utf-8"))
    assert payload["conclusion"] == "failure"


def test_a_fully_settled_no_decision_run_is_still_red_through_the_settle_gate(tmp_path, capsys):
    """A genuinely cancelled run with all rows `completed` and no decision stays `none` (red):
    the settle gate only refuses rows that are NOT terminal; a settled cancelled run is judged."""
    rc, checks = _cli(tmp_path, CANCELLED_FANOUT)
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "verdict=none" in out, out
    assert "0 failures is not a verdict" in out, out
    assert json.loads(checks.read_text(encoding="utf-8"))["conclusion"] == "failure"


def test_the_cli_refuses_to_invent_a_verdict_without_input(capsys):
    # Given no run and no job rows
    rc = cv.main([])

    # Then  it exits 2 — never 0 for "nothing to check"
    assert rc == cv.EXIT_ERROR
    assert "FAILED" in capsys.readouterr().err


def _stub_gh(tmp_path: Path, *, artifact: bool, later_run: bool) -> str:
    """A `gh` that answers the verdict's four calls — the external system, never the product's logic."""
    script = tmp_path / "gh"
    runs = {"workflow_runs": [
        {"id": 41134761297, "workflow_id": 7, "head_branch": "docs/x",
         "created_at": "2026-10-30T20:00:00Z", "conclusion": "cancelled"},
    ]}
    if later_run:
        runs["workflow_runs"].append(
            {"id": 41134761300, "workflow_id": 7, "head_branch": "docs/x",
             "created_at": "2026-10-30T20:05:00Z", "conclusion": "success"})
    artifacts = {"artifacts": ([{"name": cv.ARTIFACT}] if artifact else [])}
    run = {"id": 41134761297, "name": "CI", "head_sha": "0bd5ac6e" + "0" * 32,
           "conclusion": "cancelled", "status": "completed", "head_branch": "docs/x",
           "workflow_id": 7, "created_at": "2026-10-30T20:00:00Z"}
    payloads = {
        "/actions/runs/41134761297": run,
        "/actions/runs/41134761297/jobs": {"jobs": CANCELLED_FANOUT, "total_count": 4},
        "/actions/runs/41134761297/artifacts": artifacts,
        "/actions/runs?branch=docs/x": runs,
    }
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"payloads = {payloads!r}\n"
        f"decision = {json.dumps(decision_for(DOCS_DECISION_PATH))!r}\n"
        f"artifact_present = {artifact!r}\n"
        "argv = sys.argv[1:]\n"
        "if argv[:1] == ['run']:\n"
        "    d = argv[argv.index('-D') + 1]\n"
        "    import pathlib\n"
        "    p = pathlib.Path(d); p.mkdir(parents=True, exist_ok=True)\n"
        f"    (p / '{cv.ARTIFACT}.json').write_text(decision)\n"
        "    sys.exit(0)\n"
        "path = argv[1].split('repos/o/r', 1)[1]\n"
        "for key in sorted(payloads, key=len, reverse=True):\n"
        "    if path.startswith(key):\n"
        "        print(json.dumps(payloads[key])); sys.exit(0)\n"
        "sys.stderr.write('stub gh: no answer for ' + path + '\\n'); sys.exit(1)\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def test_a_cancelled_run_a_later_run_superseded_is_neutral_not_a_pass(tmp_path, monkeypatch, capsys):
    """Every push cancels the run above it: that head is owed nothing, and it still never reads green."""
    # Given a cancelled run with no decision artifact, and a LATER run of the same workflow
    monkeypatch.setenv("CI_VERDICT_GH", _stub_gh(tmp_path, artifact=False, later_run=True))
    checks = tmp_path / "check-run.json"

    # When  the verdict runs against the API (through the stub `gh`)
    rc = cv.main(["--repo", "o/r", "--run-id", "41134761297", "--check-run-out", str(checks)])
    out = capsys.readouterr().out

    # Then  it exits 0 — the red would be noise on a head a newer run owns — and says why
    assert rc == 0, out
    assert "SUPERSEDED by run 41134761300" in out, out

    # And  the check-run is NEUTRAL: never `success`, because this head has no verdict
    payload = json.loads(checks.read_text(encoding="utf-8"))
    assert payload["conclusion"] == "neutral", payload


def test_a_rerun_supersedes_the_attempt_it_replaced_even_with_the_same_created_at(monkeypatch):
    """#1250 Finding A: a re-run keeps the run id and created_at, bumping only run_attempt — so
    `superseding_run` must return the newer attempt as the superseder, never read attempt-1 as
    this head's final conclusion."""

    run = {"id": 41134761297, "workflow_id": 7, "head_branch": "docs/x",
           "created_at": "2026-10-30T20:00:00Z", "run_attempt": 1, "conclusion": "cancelled"}
    listing = {"workflow_runs": [
        {"id": 41134761297, "workflow_id": 7, "head_branch": "docs/x",
         "created_at": "2026-10-30T20:00:00Z", "run_attempt": 1, "conclusion": "cancelled"},
        {"id": 41134761297, "workflow_id": 7, "head_branch": "docs/x",
         "created_at": "2026-10-30T20:00:00Z", "run_attempt": 2, "conclusion": "success"},
    ]}
    monkeypatch.setattr(cv, "_api", lambda path: listing)

    superseding = cv.superseding_run("o/r", run)

    assert superseding is not None
    assert superseding.get("run_attempt") == 2


def test_a_truncated_run_listing_is_not_a_verdict_even_when_a_superseder_hides(monkeypatch):
    """#1582: `superseding_run` must refuse (never reach a verdict) when the managed listing is
    truncated — the same invariant `jobs_of` already holds. A branch with more than the returned
    page of 50 runs that cannot prove its newest superseder must not post a false `failure`."""

    run = {"id": 41134761297, "workflow_id": 7, "head_branch": "main",
           "created_at": "2026-10-30T20:00:00Z", "run_attempt": 1, "conclusion": "cancelled"}
    # total_count says 51 (matching branch=main's 2500 measured on 2026-11-02, shrunk for the
    # fixture) while the implementation-supplied page holds 50 runs with no same-workflow later run.
    page = [{"id": 100000 + i, "workflow_id": 7, "head_branch": "main",
             "created_at": "2026-10-30T19:00:00Z", "run_attempt": 1, "conclusion": "success"}
            for i in range(50)]
    listing = {"workflow_runs": page, "total_count": 51}
    monkeypatch.setattr(cv, "_api", lambda path: listing)

    # Pre-fix the listing returned the truncated page verbatim: `superseding_run` saw no later
    # same-workflow run and would have returned None — a false-red on a superseded head. The guard
    # must now refuse instead of silently returning that wrong verdict.
    try:
        cv.superseding_run("o/r", run)
    except RuntimeError as exc:
        assert "truncated listing" in str(exc)
        return
    raise AssertionError("superseding_run accepted a truncated listing as a verdict")


def test_a_non_truncated_listing_still_finds_the_superseder(monkeypatch):
    """#1582 acceptance #2: when the listing is NOT truncated the guard is silent — a later
    same-workflow same-branch run still wins, exactly as before."""

    run = {"id": 1, "workflow_id": 7, "head_branch": "main",
           "created_at": "2026-10-30T20:00:00Z", "run_attempt": 1, "conclusion": "cancelled"}
    latest = {"id": 2, "workflow_id": 7, "head_branch": "main",
              "created_at": "2026-10-30T21:00:00Z", "run_attempt": 1, "conclusion": "success"}
    listing = {"workflow_runs": [{"id": 1, "workflow_id": 7, "head_branch": "main",
                                  "created_at": "2026-10-30T20:00:00Z", "run_attempt": 1},
                                 latest], "total_count": 2}
    monkeypatch.setattr(cv, "_api", lambda path: listing)

    superseding = cv.superseding_run("o/r", run)

    assert superseding is not None
    assert superseding.get("id") == 2


def test_a_multi_page_listing_is_fully_walked_and_still_finds_the_superseder(monkeypatch):
    """#1617: a busy branch (`main` reports 2500+ runs) is split across API pages — the fetch must
    walk every page so a later run on a far page is still seen. One page of a healthy multi-page
    listing is NOT truncation; only a real shortfall is."""

    run = {"id": 1, "workflow_id": 7, "head_branch": "main",
           "created_at": "2026-10-30T20:00:00Z", "run_attempt": 1, "conclusion": "cancelled"}
    # 150 runs total (two full pages of a per_page=100 walk + a 50-row tail), the superseder last.
    page1 = [{"id": 100000 + i, "workflow_id": 7, "head_branch": "main",
              "created_at": "2026-10-30T18:00:00Z", "run_attempt": 1}
             for i in range(100)]
    page2 = [{"id": 100100 + i, "workflow_id": 7, "head_branch": "main",
              "created_at": "2026-10-30T19:00:00Z", "run_attempt": 1}
             for i in range(49)]
    superseder = {"id": 999, "workflow_id": 7, "head_branch": "main",
                  "created_at": "2026-10-30T21:00:00Z", "run_attempt": 1}
    page2.append(superseder)
    pages = {1: {"workflow_runs": page1, "total_count": 150},
             2: {"workflow_runs": page2, "total_count": 150}}

    def fake_api(path):
        page = 1
        marker = "&page="
        idx = path.find(marker)
        if idx != -1:
            page = int(path[idx + len(marker):].split("&")[0])
        return pages.get(page, {"workflow_runs": [], "total_count": 150})
    monkeypatch.setattr(cv, "_api", fake_api)

    superseding = cv.superseding_run("o/r", run)

    assert superseding is not None
    assert superseding.get("id") == 999


def test_a_genuinely_short_listing_still_raises_even_when_spread_across_pages(monkeypatch):
    """#1617/#1582: pagination fixes a FALSE truncation, never a real one. A listing whose pages
    together still fall short of `total_count` must refuse — the #1582/#1610 guard still binds.
    Here total_count=150 but the pages only ever deliver 100 rows."""

    run = {"id": 1, "workflow_id": 7, "head_branch": "main",
           "created_at": "2026-10-30T20:00:00Z", "run_attempt": 1, "conclusion": "cancelled"}
    page = [{"id": 100000 + i, "workflow_id": 7, "head_branch": "main",
             "created_at": "2026-10-30T18:00:00Z", "run_attempt": 1}
            for i in range(100)]
    pages = {1: {"workflow_runs": page, "total_count": 150},
             2: {"workflow_runs": [], "total_count": 150}}
    # the stale page is what a retried run leaves: page 2 empty, total still 150.

    def fake_api(path):
        marker = "&page="
        idx = path.find(marker)
        pg = int(path[idx + len(marker):].split("&")[0]) if idx != -1 else 1
        return pages.get(pg, {"workflow_runs": [], "total_count": 150})
    monkeypatch.setattr(cv, "_api", fake_api)

    try:
        cv.superseding_run("o/r", run)
    except RuntimeError as exc:
        assert "truncated listing" in str(exc)
        return
    raise AssertionError("superseding_run accepted a genuinely short multi-page listing as a verdict")


def test_a_cancelled_run_with_no_successor_is_red_even_through_the_api(tmp_path, monkeypatch, capsys):
    # Given a cancelled run with no decision artifact and NO later run
    monkeypatch.setenv("CI_VERDICT_GH", _stub_gh(tmp_path, artifact=False, later_run=False))
    checks = tmp_path / "check-run.json"

    # When  the verdict runs
    rc = cv.main(["--repo", "o/r", "--run-id", "41134761297", "--check-run-out", str(checks)])
    out = capsys.readouterr().out

    # Then  it exits 1 with verdict=none, and the posted check-run is a failure
    assert rc == 1, out
    assert "verdict=none" in out
    assert json.loads(checks.read_text(encoding="utf-8"))["conclusion"] == "failure"


def test_an_artifact_that_exists_but_cannot_be_downloaded_is_an_error_not_a_verdict(
        tmp_path, monkeypatch, capsys):
    """A transport failure must never be dressed up as "nobody decided"."""
    # Given a stub `gh` that lists the artifact and then fails to download it
    broken = tmp_path / "gh-broken"
    payloads = {
        "/actions/runs/41134761297": {"id": 41134761297, "name": "CI", "head_sha": "a" * 40,
                                      "head_branch": "docs/x", "workflow_id": 7,
                                      "created_at": "2026-10-30T20:00:00Z",
                                      "conclusion": "cancelled", "status": "completed"},
        "/actions/runs/41134761297/jobs": {"jobs": CANCELLED_FANOUT, "total_count": 4},
        "/actions/runs/41134761297/artifacts": {"artifacts": [{"name": cv.ARTIFACT}]},
    }
    broken.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"payloads = {payloads!r}\n"
        "argv = sys.argv[1:]\n"
        "if argv[:1] == ['run']:\n"
        "    sys.stderr.write('HTTP 502\\n'); sys.exit(1)\n"
        "path = argv[1].split('repos/o/r', 1)[1]\n"
        "for key, value in payloads.items():\n"
        "    if path.startswith(key):\n"
        "        print(json.dumps(value)); sys.exit(0)\n"
        "sys.stderr.write('no answer\\n'); sys.exit(1)\n",
        encoding="utf-8")
    broken.chmod(broken.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("CI_VERDICT_GH", str(broken))

    # When  the verdict runs
    rc = cv.main(["--repo", "o/r", "--run-id", "41134761297"])

    # Then  it is exit 2 with a FAILED line — never a `none` verdict that reads as a clean answer
    assert rc == cv.EXIT_ERROR
    err = capsys.readouterr().err
    assert "FAILED" in err and "could not reach a verdict" in err, err


# ---- 8. the wiring: published by ci.yml, consumed by ci-verdict.yml ------------------

def _workflow(name: str) -> dict:
    import yaml
    return yaml.safe_load((WF / name).read_text(encoding="utf-8"))


def _on(wf: dict) -> dict:
    """`on:` — YAML 1.1 reads the bare key as the boolean `True` (as `tests/test_ci_concurrency` does)."""
    return wf.get("on") or wf.get(True) or {}


def test_ci_yml_publishes_the_decision_artifact_the_verdict_reads():
    # Given ci.yml's guard job
    wf = _workflow("ci.yml")
    steps = wf["jobs"]["guard"]["steps"]
    runs = " ".join(step.get("run") or "" for step in steps)
    uses = [step for step in steps if step.get("uses", "").startswith("actions/upload-artifact")]

    # Then  the classifier runs through the make target, writing the decision
    assert "make ci-scope BASE=" in runs and "make ci-scope ALL=1" in runs, runs
    assert 'DECISION="$RUNNER_TEMP/ci-scope-decision.json"' in runs

    # And  the artifact is uploaded under the name the verdict reads, and a missing file is an error
    assert len(uses) == 1, [s.get("uses") for s in steps]
    assert uses[0]["with"]["name"] == cv.ARTIFACT
    assert uses[0]["with"]["if-no-files-found"] == "error"


def test_the_verdict_workflow_watches_ci_and_posts_the_check_run():
    # Given the consumer workflow
    wf = _workflow("ci-verdict.yml")
    on = _on(wf)
    jobs = wf["jobs"]

    # Then  it fires on CI's completion — any conclusion, or a cancelled run is never judged
    assert on["workflow_run"]["types"] == ["completed"]
    assert "CI" in on["workflow_run"]["workflows"]

    # And  it holds the write a check-run needs, and no other write
    assert wf["permissions"]["checks"] == "write"
    assert "contents" not in wf["permissions"] or wf["permissions"]["contents"] == "read"

    # And  no job skips itself: the verdict runs for a cancelled run, which is the whole point
    assert all("if" not in job or "always()" in str(job["if"]) for job in jobs.values()), jobs

    # And  the verdict is a make target, and the payload it wrote is what gets posted
    text = (WF / "ci-verdict.yml").read_text(encoding="utf-8")
    assert "make ci-verdict REPO=" in text
    assert 'gh api -X POST "repos/$REPO/check-runs" --input "$CHECKS_FILE"' in text
    assert "CHECK_RUN_OUT=" in text


def test_the_roster_names_this_workflow_so_a_red_verdict_is_routed():
    """A red verdict must have a consumer (`run-failure-reactor`), or this is a control nobody watches."""
    name = _workflow("ci-verdict.yml")["name"]
    reactor = _workflow("run-failure-reactor.yml")

    roster = _on(reactor)["workflow_run"]["workflows"]
    assert name in roster, roster


def test_the_judge_job_key_does_not_collide_with_the_authoritative_check_run_name():
    """GitHub's auto job check-run is named after the job KEY on the DEFAULT-branch head, so a
    `judge`-shaped run judging a PR must not also be named `verdict` (#1871).

    Before #1871 the job key was `verdict`, so a green `main` tip showed BOTH the posted
    `ci-verdict: success` (the tip's own verdict, posted at the judged head by #1864) AND an auto
    `verdict` job row that belonged to a judged PR (measured at `5bb742b2c2`, runs `42244374725` /
    `42244789060`, grading PR #1870's stale base). A reader on the tip could not tell the red apart
    from a tip failure. The job is renamed `judge` so the ONLY "verdict"-named check-run is the
    posted, authoritative one.
    """
    wf = _workflow("ci-verdict.yml")
    assert "verdict" not in wf["jobs"], wf["jobs"].keys()
    assert "judge" in wf["jobs"], wf["jobs"].keys()
    # the authoritative posted check-run keeps its distinct, reader-facing name
    text = (WF / "ci-verdict.yml").read_text(encoding="utf-8")
    assert "make ci-verdict REPO=" in text
    assert "ci-verdict" not in wf["jobs"], "the auto job row must not steal the posted check-run name"


# ---- 9. a post-merge straggler (a run on a branch whose PR is already merged) ----------

#: Run 41948125618 @ 8bc3be7d — measured 2026-11-05. A `pull_request` run created 01:22:53Z, ~24
#: min after #1737 merged (00:58:13Z) on a branch since deleted; `pull_requests` came back `[]`.
MERGED_PR = {"number": 1737, "state": "closed", "merged": True, "head": {"sha": "8bc3be7d" + "0" * 33}}
OPEN_PR = {"number": 111, "state": "open", "merged": False, "head": {"sha": "8bc3be7d" + "0" * 33}}


def test_merged_pr_run_detects_a_run_whose_pull_request_is_merged(monkeypatch):
    """The straggler's own run row carries `pull_requests` when the branch still resolves."""
    run = {"event": "pull_request", "pull_requests": [{"number": 1737}]}
    monkeypatch.setattr(cv, "_api", lambda path: MERGED_PR)

    assert cv.merged_pr_run("o/r", run) == MERGED_PR


def test_merged_pr_run_resolves_a_deleted_branch_by_head_sha(monkeypatch):
    """`pull_requests` is `[]` once the branch is deleted — fall back to a head-sha lookup."""
    calls = []

    def fake_api(path):
        calls.append(path)
        return [MERGED_PR]

    run = {"event": "pull_request", "pull_requests": [],
           "head_branch": "fix/top-tier-pick-size-threshold", "head_sha": "8bc3be7d" + "0" * 33}
    monkeypatch.setattr(cv, "_api", fake_api)

    assert cv.merged_pr_run("o/r", run) == MERGED_PR
    assert any("state=all&head=fix/top-tier-pick-size-threshold" in c for c in calls), calls


def test_merged_pr_run_returns_none_for_an_open_or_unmerged_pr(monkeypatch):
    """A PR that is NOT yet merged is not a straggler — its run can still decide, so it stays judged."""
    monkeypatch.setattr(cv, "_api", lambda path: OPEN_PR)
    run = {"event": "pull_request", "pull_requests": [{"number": 111}]}

    assert cv.merged_pr_run("o/r", run) is None


def test_merged_pr_run_ignores_non_pull_request_events():
    """A `push`-event run on a branch is not a straggler — only PR runs can have a merged PR."""
    assert cv.merged_pr_run("o/r", {"event": "push", "head_branch": "main"}) is None


def _stub_gh_straggler(tmp_path: Path, pr) -> str:
    """A `gh` that answers the verdict's calls PLUS the merged-PR lookup, driving the real logic."""
    script = tmp_path / "gh"
    run = {"id": 41948125618, "name": "CI", "head_sha": "8bc3be7d" + "0" * 33,
           "conclusion": "failure", "status": "completed",
           "head_branch": "fix/top-tier-pick-size-threshold", "workflow_id": 7,
           "created_at": "2026-11-05T01:22:53Z", "event": "pull_request",
           "pull_requests": []}
    runs = {"workflow_runs": [run], "total_count": 1}
    artifacts = {"artifacts": []}
    straggler_jobs = [
        {"name": "guard", "status": "completed", "conclusion": "failure"},
        {"name": "linux", "status": "completed", "conclusion": "skipped"},
        {"name": "ci-images", "status": "completed", "conclusion": "skipped"},
        {"name": "scanner-images", "status": "completed", "conclusion": "skipped"},
    ]
    payloads = {
        "/actions/runs/41948125618": run,
        "/actions/runs/41948125618/jobs": {"jobs": straggler_jobs, "total_count": 4},
        "/actions/runs/41948125618/artifacts": artifacts,
        "/actions/runs?branch=fix/top-tier-pick-size-threshold": runs,
        "/pulls?state=all&head=fix/top-tier-pick-size-threshold": [pr],
    }
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"payloads = {payloads!r}\n"
        f"merged = {json.dumps(pr)!r}\n"
        "argv = sys.argv[1:]\n"
        "if argv[:1] == ['run']:\n"
        "    d = argv[argv.index('-D') + 1]\n"
        "    import pathlib\n"
        "    p = pathlib.Path(d); p.mkdir(parents=True, exist_ok=True)\n"
        "    sys.exit(0)\n"
        "path = argv[1].split('repos/o/r', 1)[1]\n"
        "for key in sorted(payloads, key=len, reverse=True):\n"
        "    if path.startswith(key):\n"
        "        print(json.dumps(payloads[key])); sys.exit(0)\n"
        "if path.startswith('/pulls?'):\n"
        "    print(json.dumps([merged])); sys.exit(0)\n"
        "sys.stderr.write('stub gh: no answer for ' + path + '\\n'); sys.exit(1)\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def test_a_merged_branch_straggler_is_neutral_never_red(tmp_path, monkeypatch, capsys):
    """#1730-class: a run on a branch whose PR already merged can never publish a scope decision, and
    must not red the head — neutral, exactly like a superseded head."""
    monkeypatch.setenv("CI_VERDICT_GH", _stub_gh_straggler(tmp_path, MERGED_PR))
    checks = tmp_path / "check-run.json"

    rc = cv.main(["--repo", "o/r", "--run-id", "41948125618", "--check-run-out", str(checks)])
    out = capsys.readouterr().out

    # Then  it exits 0 (no red on a straggler) and names the reason
    assert rc == 0, out
    assert "MERGED-BRANCH STRAGGLER" in out and "#1737" in out, out

    # And  the check-run is NEUTRAL: never success, so the head never reads as a pass
    payload = json.loads(checks.read_text(encoding="utf-8"))
    assert payload["conclusion"] == "neutral", payload


def test_an_open_pr_run_with_no_decision_is_still_red(tmp_path, monkeypatch, capsys):
    """The gate must not be weakened: an open PR's run with no decision still reds — only a MERGED
    PR's straggler is neutral."""
    monkeypatch.setenv("CI_VERDICT_GH", _stub_gh_straggler(tmp_path, OPEN_PR))
    checks = tmp_path / "check-run.json"

    rc = cv.main(["--repo", "o/r", "--run-id", "41948125618", "--check-run-out", str(checks)])
    out = capsys.readouterr().out

    # Then  it still reds (no decision + a failing guard, no merged PR to make it neutral),
    # and the straggler path is NOT taken — the gate is not weakened
    assert rc == 1, out
    assert "MERGED-BRANCH STRAGGLER" not in out, out
    payload = json.loads(checks.read_text(encoding="utf-8"))
    assert payload["conclusion"] == "failure", payload


def test_the_dispatch_rejudge_path_is_declared_and_self_sufficient_for_head():
    """PR #1887 (issue #1886): ci-verdict.yml MUST declare a workflow_dispatch re-judge (run_id input)
    and, for a bare run_id dispatch (no head_sha input), resolve HEAD_SHA from the judged run itself —
    never post a check-run with an empty head. The auto workflow_run path is unchanged."""
    wf = _workflow("ci-verdict.yml")
    on = _on(wf)
    disp = on.get("workflow_dispatch") or {}
    inputs = (disp.get("inputs") or {})
    # the dispatch trigger with the run_id input the re-judge is driven by
    assert "workflow_run" in on and "workflow_dispatch" in on, list(on)
    assert "run_id" in inputs, inputs
    # the run_id input is required, so a dispatch always names one run to re-judge
    assert inputs["run_id"].get("required") is True, inputs["run_id"]
    # the made step resolves HEAD_SHA from the run's own head when the input is omitted
    text = (WF / "ci-verdict.yml").read_text(encoding="utf-8")
    assert "$RUNNER_TEMP/verdict/head_sha" in text          # we persist the resolved head
    assert "gh api \"repos/$REPO/actions/runs/$RUN_ID\"" in text  # we read the run's head via API
    assert "cat \"$RUNNER_TEMP/verdict/head_sha\"" in text   # the make step consumes the file
    # the auto workflow_run trigger is not displaced by the addition
    assert on["workflow_run"]["types"] == ["completed"]
    assert "CI" in on["workflow_run"]["workflows"]
