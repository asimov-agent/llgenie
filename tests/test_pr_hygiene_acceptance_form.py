"""`make check-pr-acceptance-form` refuses a BOT PR whose body has no own `## Acceptance criteria` `- [ ]` checklist (issue #1796).

The owner's universal form rule: every issue a fleet lane files AND every PR body it opens carries a
`## Acceptance criteria` section with each criterion a `- [ ]` markdown checkbox, one per provable
outcome; a criterion a reviewer cannot tick is not one (#745). This is the PR-BODY half of that rule
(the merge-time #1792 gate already verifies the LINKED ISSUE's criteria are *ticked*). It is
verification/surface only — never a #1088 merge-blocker, never a tick (that stays #1644). The gate is
bot-gated via `is_bot_pr` (a human-only range is skipped, exactly like `check-pr-agents-line`).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts import check_pr_hygiene as hy  # noqa: E402  (one import root, issue #796; paths via tests/conftest.py)

REPO = Path(__file__).resolve().parent.parent


def git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def commit(root: Path, rel: str, message: str,
           name: str = "Asimov Agent", email: str = "support@docondee.com") -> str:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"content for {rel}\n")
    git(root, "add", "-A")
    git(root, "-c", f"user.name={name}", "-c", f"user.email={email}", "commit", "-q", "-m", message)
    return git(root, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    commit(root, "base.txt", "base")
    git(root, "checkout", "-q", "-b", "feature")
    commit(root, "work.txt", "work")  # bot-authored: the feature range carries bot identity
    return root


def _body() -> str:
    return ("closes #1000\n\n"
            "## What and why\n\nbody text\n\n"
            "## Technical\n\n- details\n")


def _body_with_criteria() -> str:
    return ("closes #1000\n\n"
            "## What and why\n\nbody text\n\n"
            "## Acceptance criteria\n\n"
            "- [ ] criterion one is met\n"
            "- [ ] criterion two is met\n\n"
            "## Technical\n\n- details\n")


def test_a_bot_pr_with_no_acceptance_checklist_is_a_finding(repo: Path):
    head = git(repo, "rev-parse", "feature")
    items = hy.pr_acceptance_form_findings(repo, "feature", "main", _body())
    assert [i["key"] for i in items] == ["acceptance-form"]
    assert "## Acceptance criteria" in items[0]["detail"]


def test_a_bot_pr_with_empty_acceptance_section_is_a_finding(repo: Path):
    body = _body().replace("## Technical", "## Acceptance criteria\n\n\n## Technical")
    items = hy.pr_acceptance_form_findings(repo, "feature", "main", body)
    assert [i["key"] for i in items] == ["acceptance-form"]


def test_a_bot_pr_with_a_real_checklist_passes(repo: Path):
    assert hy.pr_acceptance_form_findings(repo, "feature", "main", _body_with_criteria()) == []


def test_a_human_only_range_is_skipped(repo: Path):
    # A human-only feature range (no bot commit) must be skipped — the rule is stated for fleet lanes.
    git(repo, "checkout", "-q", "main")
    git(repo, "checkout", "-q", "-b", "human-only")
    commit(repo, "h.txt", "human work", name="Andy", email="andy.holst@protonmail.com")
    assert hy.is_bot_pr(repo, "main", "human-only") is False
    assert hy.pr_acceptance_form_findings(repo, "human-only", "main", _body()) == []


def test_the_acceptance_form_gate_is_wired_and_reuses_writeback(repo: Path):
    """The #1796 form gate must actually RUN and reuse acceptance_writeback — not just exist as a subcommand.

    ci.yml is the merge gate (it runs the full guard sequence, so the form preflight must sit
    BEFORE the issue-state gate there to unmask its verdict, #1796). scope.yml is the docs/scope
    gate — it runs the live-body-read form preflight too (the live-body read is the same shape as
    every sibling gate, issue #1589), but it is not the merge gate so it need not carry the
    issue-state step. Assert both files run the form step with a live-body read, and ci.yml's order.
    """
    for rel in (".github/workflows/ci.yml", ".github/workflows/scope.yml"):
        txt = (REPO / rel).read_text()
        assert "make check-pr-acceptance-form" in txt, f"{rel} must run the #1796 form preflight"
        # the form step's own block carries a live-body read (gh api) or a no-body fallback
        i = txt.index("make check-pr-acceptance-form")
        block = txt[i:i + 1200]
        assert "gh api" in block or "PR_BODY" in block, f"{rel}: form step must read the live PR body"
    # ci.yml order: the form step appears BEFORE the issue-state gate (#1796 unmasks the verdict).
    # Anchor on the step-NAME lines: "make check-pr-acceptance-form" is a prefix-collision with the
    # issue-state step's target, so match "name: make check-pr-acceptance (" (the issue-state step
    # name) after "name: make check-pr-acceptance-form" (the form step name) to avoid comparing the
    # substring host to itself.
    ci = (REPO / ".github/workflows/ci.yml").read_text()
    form_name = "name: make check-pr-acceptance-form"
    acc_name = "name: make check-pr-acceptance ("
    assert form_name in ci and acc_name in ci
    assert ci.index(form_name) < ci.index(acc_name)
    # reuse, never restate: the implementation imports acceptance_items (issue #1796)
    impl = (REPO / "scripts" / "check_pr_hygiene.py").read_text()
    assert "acceptance_writeback" in impl and "acceptance_items" in impl
