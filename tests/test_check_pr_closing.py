from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import check_pr_closing as cpc  # noqa: E402
from check_pr_closing import main as run_cli  # noqa: E402

FIXTURES = REPO / "tests" / "fixtures"
PR1328 = FIXTURES / "pr-1328-body.md"   # the no-keyword defect: left #1327 open
PR1326 = FIXTURES / "pr-1326-body.md"   # the control: 'Fixes #1322' closed correctly
AGENT_HEAD = "agent/issue-1327-fold-round10"


# --- adjacency is the rule: the regex must mirror GitHub's actual parser --------------------


def test_adjacent_keyword_closes():
    assert cpc.closing_references("closes #1327") == ["1327"]


def test_markdown_between_keyword_and_ref_does_NOT_close():
    # The measured #1328 defect: 'Addresses and closes **#1327**' left #1327 OPEN.
    assert cpc.closing_references("Addresses and closes **#1327**") == []


def test_colon_or_no_space_does_NOT_close():
    assert cpc.closing_references("closes:#1327") == []
    assert cpc.closing_references("closes#1327") == []


def test_every_keyword_form_matches():
    for body in ("fix #1", "fixes #1", "fixed #1", "close #1", "closes #1",
                 "closed #1", "resolve #1", "resolves #1", "resolved #1", "CLOSES #99"):
        assert cpc.closing_references(body) != [], body


def test_multiple_keyword_forms_in_one_body():
    assert cpc.closing_references("fixes #1 and closes #2") == ["1", "2"]


def test_any_ref_captures_numbers_regardless_of_keyword():
    assert "1327" in cpc.referenced_issues("Addresses and closes **#1327**")


# --- the fixture pair (issue #1329's historical regression) ----------------------------------


def test_pr_1328_body_carries_no_closing_keyword__the_defect():
    # Reference adjacency is the point: the body literally says 'closes **#1327**', which GitHub
    # never parsed — that is the exact measured failure (#1327 left open).
    assert cpc.closing_references(PR1328.read_text()) == []


def test_pr_1326_body_closes_1322__the_control():
    assert cpc.closing_references(PR1326.read_text()) == ["1322"]


# --- the gate: an agent/* PR must close its issue --------------------------------------------


def test_agent_pr_without_closing_keyword_is_RED(monkeypatch):
    monkeypatch.chdir(REPO)  # root defaults to REPO for the AGENTS.md half
    finding = cpc.check_body(PR1328, AGENT_HEAD)
    assert finding, "the fixture-documented defect must be red"
    keys = [f["key"] for f in finding]
    assert any("closing/" in k for k in keys), keys
    assert any("1327" in f["evidence"] for f in finding)


def test_agent_pr_with_closing_keyword_is_GREEN(monkeypatch):
    monkeypatch.chdir(REPO)
    assert cpc.check_body(PR1326, "agent/issue-1322-engine-host") == []


def test_non_agent_head_is_out_of_scope(monkeypatch):
    monkeypatch.chdir(REPO)
    # The owner's own branches (charts, renovate bumps, direct pushes) are not the implementing lane.
    assert cpc.check_body(PR1328, "test-engine-host") == []
    assert cpc.check_body(PR1328, "renovate/bump-x") == []


def test_markdown_wrapped_keyword_is_RED_even_with_a_ref(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO)
    p = tmp_path / "body.md"
    p.write_text("Addresses and closes **#1327**. Never merged.")
    finding = cpc.check_body(p, AGENT_HEAD)
    assert any("closing/" in f["key"] for f in finding), finding


def test_agents_mandate_absent_is_RED(tmp_path, monkeypatch):
    # A bare tree with no AGENTS.md mandate reds the checker even when the PR body is green — the
    # rule cannot be deleted silently by a PR whose own body carries the keyword.
    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / "AGENTS.md").write_text("# not the mandate")
    monkeypatch.chdir(REPO)
    p = bare / "body.md"
    p.write_text("closes #1327")
    finding = cpc.check_body(p, AGENT_HEAD, root=bare)
    assert any(f["key"] == "agents-mandate" for f in finding), finding


# --- CLI check/report round-trips -------------------------------------------------------------


def test_cli_check_and_report(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO)
    p = tmp_path / "body.md"
    p.write_text("This fixes #9 today.")
    # report is informational and always green
    assert run_cli(["report", "--body-file", str(p), "--head", "renovate/x"]) == 0
    # agent head with a valid 'fixes #9' -> OK
    assert run_cli(["check", "--body-file", str(p), "--head", AGENT_HEAD]) == 0
    p.write_text("Addresses but never closes **#9**")
    assert run_cli(["check", "--body-file", str(p), "--head", AGENT_HEAD]) != 0
