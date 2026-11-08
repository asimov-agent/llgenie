"""The check-run posters and the set `ci-verdict` judges are two different populations (#2116).

`ci-verdict` judged exactly ONE workflow (`CI`) while `scripts/auto_merge.py` refuses a merge on ANY
red check-run at the head (#1386). Measured specimen, PR #1982 head `aeac049f`: `ci-verdict: success`,
`autoMergeRequest` armed, and `engine-build-pr-trigger` `failure` (run 42440650801) — a head that was
green on the one surface every reader trusts and unmergeable in fact.

`scripts/verdict_roster.py` is the roster half: every workflow that can post a check-run at a PR head
must carry a dated judgement decision, and the judged set must be a SUBSET of the posters (`judged <=
posters`, never equality — the workflow set grows by design). `scripts/ci_verdict.py` is the runtime
half (its cases live in tests/test_ci_verdict.py): it names the red it did not judge.

The negative control is `test_a_new_pull_request_workflow_with_no_decision_reds_the_gate`: delete the
decision entry for one poster and the gate reds, naming that file.
"""
from __future__ import annotations

import json
from pathlib import Path

import scripts.check_workflows as cw
import scripts.verdict_roster as vr

REPO = Path(__file__).resolve().parents[1]

VERDICT_WORKFLOW = """name: ci-verdict
on:
  workflow_run:
    workflows:
      - CI
    types: [completed]
"""

CI_WORKFLOW = """name: CI
on:
  pull_request:
  push:
    branches: [main]
jobs:
  guard:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
"""


def _tree(tmp_path: Path, workflows: dict[str, str], decisions: dict[str, dict]) -> Path:
    """A repository-shaped tree: the workflow files and the decision file, nothing else."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    for name, text in workflows.items():
        (wf / name).write_text(text, encoding="utf-8")
    data = tmp_path / "data"
    data.mkdir()
    (data / "verdict-roster.json").write_text(
        json.dumps({"schema": 1, "workflows": decisions}), encoding="utf-8")
    return tmp_path


# ---- 1. the shipped tree is green, and the check is a SUBSET ------------------------

def test_the_shipped_tree_carries_a_decision_for_every_poster_and_judges_a_subset():
    # Given the real workflow tree
    posters = vr.poster_workflows(REPO)
    judged = vr.judged_workflows(REPO)

    # When  the roster gate reads it
    items = vr.coverage(REPO)

    # Then  every poster carries a dated decision and nothing is stale
    assert items == [], items

    # And  the judged set is a SUBSET of the posters, never an equality
    assert judged <= set(posters.values()), (judged, posters)

    # And  the measured difference is exactly the three check-run posters outside the verdict
    assert vr.difference(REPO) == ["engine-build-pr-trigger.yml", "holds.yml", "scope.yml"], \
        vr.difference(REPO)


def test_every_decision_outside_the_judged_set_carries_its_reason_date_and_issue():
    decisions = vr.decisions(REPO)
    judged_files = vr.judged_files(REPO)

    for filename, decision in decisions.items():
        if decision.get("judged"):
            assert filename in judged_files, (filename, judged_files)
            continue
        for field in ("reason", "date", "issue"):
            assert decision.get(field), (filename, field, decision)


# ---- 2. the gate reds on an unrecorded poster (the sabotage) ------------------------

def test_a_new_pull_request_workflow_with_no_decision_reds_the_gate(tmp_path, monkeypatch, capsys):
    """The negative control: plant a `pull_request` workflow with no decision, and the gate reds.

    Pre-fix there was no such rule at all — a new `pull_request` workflow joined the merge-gate
    population silently. The gate is `make check-workflows`, and this drives its real `findings()`.
    """
    # Given a tree whose poster population has grown by one workflow nobody decided about
    root = _tree(
        tmp_path,
        {"ci-verdict.yml": VERDICT_WORKFLOW, "ci.yml": CI_WORKFLOW,
         "new-harness.yml": "name: new-harness\non:\n  pull_request:\n"},
        {"ci.yml": {"judged": True}},
    )
    monkeypatch.chdir(root)

    # When  the workflow gate reads that tree
    items = cw.findings(root)
    text = cw.render(items)

    # Then  it reds, naming the file that has no judgement decision
    assert cw.main(["check", "--root", str(root)]) == 1
    assert "verdict-roster-unrecorded/new-harness.yml" in [item["key"] for item in items], items
    assert "new-harness.yml can post a check-run at a PR head and has no judgement decision" in text, text


def test_a_stale_decision_is_reported_not_ignored(tmp_path):
    # Given a decision for a workflow that no longer has a pull_request trigger
    root = _tree(
        tmp_path,
        {"ci-verdict.yml": VERDICT_WORKFLOW, "ci.yml": CI_WORKFLOW},
        {"ci.yml": {"judged": True}, "gone.yml": {"judged": False, "reason": "r",
                                                  "date": "2026-11-08", "issue": 1}},
    )

    # When  the roster reads it
    keys = [item["key"] for item in vr.coverage(root)]

    # Then  the stale entry is named, so the roster cannot rot in the other direction
    assert "verdict-roster-stale/gone.yml" in keys, keys


def test_a_decision_that_claims_judged_but_is_absent_from_the_roster_reds(tmp_path):
    # Given `judged: true` for a workflow ci-verdict.yml does not list
    root = _tree(
        tmp_path,
        {"ci-verdict.yml": VERDICT_WORKFLOW, "ci.yml": CI_WORKFLOW,
         "scope.yml": "name: ci-scope\non:\n  pull_request:\n"},
        {"ci.yml": {"judged": True}, "scope.yml": {"judged": True}},
    )

    # When  the roster reads it
    keys = [item["key"] for item in vr.coverage(root)]

    # Then  the lie is a finding: those reds would be invisible to a `ci-verdict: success`
    assert "verdict-roster-not-judged/scope.yml" in keys, keys


def test_an_undated_exemption_is_a_finding(tmp_path):
    # Given a poster left outside the verdict with no reason/date/issue
    root = _tree(
        tmp_path,
        {"ci-verdict.yml": VERDICT_WORKFLOW, "ci.yml": CI_WORKFLOW,
         "scope.yml": "name: ci-scope\non:\n  pull_request:\n"},
        {"ci.yml": {"judged": True}, "scope.yml": {"judged": False}},
    )

    # When  the roster reads it
    keys = [item["key"] for item in vr.coverage(root)]

    # Then  an undated exemption is indistinguishable from a forgotten row
    assert "verdict-roster-undated/scope.yml" in keys, keys


# ---- 3. growth is allowed: the check is a subset, not an equality -------------------

def test_a_new_pull_request_workflow_with_a_decision_keeps_the_gate_green(tmp_path):
    """A roster that asserted equality would red on the next legitimate addition."""
    # Given a tree that gained a poster AND recorded the decision for it
    root = _tree(
        tmp_path,
        {"ci-verdict.yml": VERDICT_WORKFLOW, "ci.yml": CI_WORKFLOW,
         "harness.yml": "name: harness\non:\n  pull_request:\n"},
        {"ci.yml": {"judged": True},
         "harness.yml": {"judged": False, "reason": "own gate", "date": "2026-11-08", "issue": 2}},
    )

    # When  the roster reads it
    items = vr.coverage(root)

    # Then  growth with a decision is green — no equality assertion
    assert items == [], items


# ---- 4. the report names both populations and the difference -----------------------

def test_the_report_prints_the_posters_the_judged_set_and_the_difference():
    text = vr.report(REPO)

    assert "[verdict-roster] posters (" in text
    assert "[verdict-roster] judged (" in text
    assert "[verdict-roster] NOT judged (3)" in text
    assert "engine-build-pr-trigger.yml" in text and "ci.yml  <CI>" in text
    assert "verdict: green" in text
