from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from scripts import check_pr_acceptance as g
from scripts.check_pr_acceptance import main as run_cli

REPO = Path(__file__).resolve().parents[1]


def _issue(ticked: list[int], total: int, extra: str = "") -> str:
    """A repo-shaped issue body with `total` acceptance criteria, `ticked` of them proven."""
    lines = ["## Problem", "", "measured defect", "", "## How we fix it", "", "1. fix it", "",
             "## Benefit", "", "done", "", "## Acceptance criteria", ""]
    for i in range(1, total + 1):
        state = "x" if i in ticked else " "
        lines.append(f"- [{state}] criterion {i} is met")
    lines += ["", "## Technical", "", "- details", ""]
    if extra:
        lines += extra.splitlines() + [""]
    return "\n".join(lines).rstrip("\n") + "\n"


def _pr(closes: str, criteria_text: str = "closes #1000", body_checkbox: str = "") -> str:
    """A PR body that closes `closes`, optionally carrying its own `- [x]` claim."""
    lines = ["## What and why", "", f"{closes}", "", criteria_text, ""]
    if body_checkbox:
        lines += ["### Verify", "", body_checkbox, ""]
    return "\n".join(lines).rstrip("\n") + "\n"


# --- the gate: a close must meet the issue's own done -------------------------------------------------


def test_closed_issue_with_unticked_criterion_is_RED():
    # 5/5 unmarked, #491-class: the merged PR closes it and CI verifies green in the status quo.
    findings = g.acceptance_verdict(_issue(ticked=[], total=5), _pr("closes #1000"))
    assert findings, "a closed issue with 5/5 unticked must be red"
    assert any(f["key"] == "acceptance-unchecked" for f in findings), [f["key"] for f in findings]


def test_closed_issue_with_all_criteria_ticked_is_GREEN():
    assert g.acceptance_verdict(_issue(ticked=[1, 2, 3], total=3), _pr("closes #1000")) == []


def test_partially_ticked_issue_is_RED_on_the_unchecked():
    findings = g.acceptance_verdict(_issue(ticked=[1], total=3), _pr("closes #1000"))
    assert any(f["key"] == "acceptance-unchecked" for f in findings)
    # the proven item 1 is not named a violation
    assert "item 1" not in ",".join(f["evidence"] for f in findings)


def test_issue_with_no_acceptance_section_is_GREEN():
    # nothing to prove — the repository shape requires the section, but a foreign/no-criteria issue
    # must not be held to criteria it does not declare.
    body = "## Problem\n\nx\n## Technical\n\n- t\n"
    assert g.acceptance_verdict(body, _pr("closes #1000")) == []


def test_out_of_scope_with_linked_work_item_is_GREEN():
    # The exemption: the close is held UNLESS the PR names the criterion as out of scope with a
    # linked work item under `## Not covered`.
    issue = _issue(ticked=[], total=1)
    pr = _pr("closes #1000", criteria_text="criterion 1 is deferred") + (
        "\n## Not covered\n- criterion 1 is met is tracked as #1001\n")
    assert g.acceptance_verdict(issue, pr) == []


def test_bare_out_of_scope_claim_with_no_linked_issue_is_RED():
    issue = _issue(ticked=[], total=1)
    pr = "closes #1000\n## Not covered\n- criterion 1 is met is out of scope, trust me\n"
    assert any(f["key"] == "acceptance-unchecked" for f in g.acceptance_verdict(issue, pr))


# --- claim-exceeds: the PR body must not tick what the issue has open ---------------------------------


def test_pr_body_ticking_an_issue_unticked_criterion_is_RED():
    issue = _issue(ticked=[1], total=2)      # item 2 is open in the issue
    pr = _pr("closes #1000", body_checkbox="- [x] criterion 2 is met")
    assert any(f["key"] == "acceptance-exceeds" for f in g.acceptance_verdict(issue, pr))


def test_pr_body_claim_matching_a_ticked_criterion_is_GREEN():
    issue = _issue(ticked=[1, 2], total=2)     # both criteria proven in the issue
    pr = _pr("closes #1000", body_checkbox="- [x] criterion 1 is met")
    assert g.acceptance_verdict(issue, pr) == []


# --- CLI: live issue read at merge time ---------------------------------------------------------------


def _fake_gh(tmp_path: Path, issue_body: str, monkeypatch) -> None:
    """A `gh` on PATH answering `issue view N --json body` from a sidecar file.

    The sidecar keeps the issue body's real newlines out of the script source, so the detector cannot
    misread an f-string/escaping artifact for a live response.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "issue.json").write_text(json.dumps({"body": issue_body}))
    gh = bindir / "gh"
    gh.write_text(
        "#!/usr/bin/env python3\nimport json, sys, os\n"
        "if sys.argv[1:3] == ['issue', 'view']:\n"
        "    here = os.path.dirname(os.path.abspath(__file__))\n"
        "    print(open(here + '/issue.json').read()); sys.exit(0)\n"
        "sys.exit(1)\n")
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")


def test_cli_check_red_on_an_unticked_issue(tmp_path, monkeypatch):
    # drive the real CLI with a fake gh answering `issue view N --json body`
    _fake_gh(tmp_path, _issue(ticked=[], total=2), monkeypatch)
    body = tmp_path / "pr.md"
    body.write_text("closes #1000\n")
    assert run_cli(["check", "--body-file", str(body)]) != 0


def test_cli_check_green_when_ticked(tmp_path, monkeypatch):
    _fake_gh(tmp_path, _issue(ticked=[1, 2], total=2), monkeypatch)
    body = tmp_path / "pr.md"
    body.write_text("closes #1000\n")
    assert run_cli(["check", "--body-file", str(body)]) == 0


def test_cli_report_lists_counts(tmp_path, monkeypatch):
    _fake_gh(tmp_path, _issue(ticked=[1], total=3), monkeypatch)
    body = tmp_path / "pr.md"
    body.write_text("closes #1000\n")
    assert run_cli(["report", "--body-file", str(body)]) == 0


def test_cli_no_close_is_green(tmp_path):
    # a PR that closes nothing has no linked issue to hold — green, every time.
    body = tmp_path / "pr.md"
    body.write_text("a routine change with no issue\n")
    assert run_cli(["check", "--body-file", str(body)]) == 0
