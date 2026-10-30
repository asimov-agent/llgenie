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
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import ci_scope as cs  # noqa: E402
import ci_verdict as cv  # noqa: E402

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
