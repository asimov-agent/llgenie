#!/usr/bin/env python3
"""A bot PR's description comes from the run, never from a fixed string (issue #429).

`make issue-bot-open-pr` was hardcoded:

    --title "issue-bot implementation" --wants "Verification notes land on the PR as CI runs it."

and `open_pr()` built `f"{body}\\n\\ncloses #{num}\\n{wants}"` with `body=""`, so every bot PR opened with
the same three lines — no issue, no fix, no benefit, no files — while carrying `closes #<n>`. PR #424 is
exactly that: an empty-looking body over a one-line diff, and `make check-pr-hygiene` could not see it
because it reads the producer's SOURCE text (`f"{body}\\n\\ncloses …"` is neither empty nor a known
placeholder), never the rendered body.

These cases are the rendered check: the body is validated from a real file, the four AGENTS.md parts are
required, the file list comes from git, and a missing or thin body refuses to open the PR at all.

NO-SKIP POLICY: every case runs the real functions; none is skipped.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(REPO / "scripts"))
import issue_implementer as ii  # noqa: E402

MAKEFILE = (REPO / "Makefile").read_text()

GOOD = (
    "Issue: #11 — the smoke proves a sentence, not a tool call\n\n"
    "Fix: the smoke drives a real terminal call and asserts the transcript.\n\n"
    "Benefit: a model with broken tool calling reds in seconds instead of after two hours.\n\n"
    "Technical: scripts/hermes_smoke.py, Makefile, tests/test_hermes_smoke.py.\n"
)


def test_a_missing_pr_body_file_refuses_the_pr(monkeypatch, tmp_path):
    """No body file, no PR: a description that says nothing must not exist."""

    # Given a bot that produced no pr-body.md
    calls: list[list[str]] = []
    monkeypatch.setattr(ii, "_gh", lambda gh, args: calls.append(args) or "https://x.invalid/pull/9")

    # When  the PR is opened
    with pytest.raises(SystemExit) as refused:
        ii.open_pr("gh", "o/r", 11, "agent/issue-11-s", "fix(x): t", str(tmp_path / "pr-body.md"))

    # Then  it refuses, naming the file and the labels, and never calls gh
    assert "pr-body.md" in str(refused.value), refused.value
    assert "Issue:" in str(refused.value), refused.value
    assert calls == [], calls


def test_a_body_missing_a_part_is_refused():
    """Every AGENTS.md part is required, and the refusal names the one that is absent."""

    # Given a body with no `Benefit:` part
    thin = "Issue: #11 — x\n\nFix: y\n\nTechnical: scripts/x.py\n"

    # When  it is rendered
    with pytest.raises(SystemExit) as refused:
        ii.render_pr_body(thin, 11, " scripts/x.py | 1 +\n")

    # Then  the missing part is named
    assert "Benefit:" in str(refused.value), refused.value


def test_a_part_with_no_content_is_refused():
    """A label with nothing after it is the placeholder defect in another spelling."""

    # Given a body whose `Fix:` states nothing
    empty = "Issue: #11 — x\n\nFix:   \n\nBenefit: z\n\nTechnical: scripts/x.py\n"

    # When  it is rendered
    with pytest.raises(SystemExit) as refused:
        ii.render_pr_body(empty, 11, "")

    # Then  the empty part is named
    assert "Fix:" in str(refused.value), refused.value


def test_a_body_that_does_not_name_the_issue_is_refused():
    """The body must name the issue it implements, not just close it."""

    # Given a complete body that names no issue
    unnamed = GOOD.replace("#11", "the issue")

    # When  it is rendered for #11
    with pytest.raises(SystemExit) as refused:
        ii.render_pr_body(unnamed, 11, "")

    # Then  the missing reference is named
    assert "#11" in str(refused.value), refused.value


def test_a_real_body_carries_the_four_parts_the_stat_and_the_closes_marker():
    """The composed body is the agent's four parts plus the commit's own file list."""

    # Given a real four-part body and the commit's stat
    stat = " scripts/hermes_smoke.py | 120 ++++++++++++++++++++\n 1 file changed, 120 insertions(+)\n"

    # When  it is rendered
    body = ii.render_pr_body(GOOD, 11, stat)

    # Then  every part, the file list and the closing marker are present, in that order
    for part in ii.PR_PARTS:
        assert part in body, body
    assert "Files changed:" in body and "scripts/hermes_smoke.py" in body, body
    assert body.rstrip().endswith("closes #11"), body
    assert body.index("Issue:") < body.index("Fix:") < body.index("Benefit:") < body.index("Technical:")


def test_the_title_is_the_issues_typed_subject_or_a_typed_prefix():
    """The subject is a Conventional Commit derived from the issue, never a fixed string."""

    # Given an issue whose title already carries a type, and one that does not
    typed = ii.pr_title("ci(bots): the smoke proves a tool call", 407)
    untyped = ii.pr_title("Make the smoke prove a tool call", 407)

    # When  the PR subjects are built
    # Then  the typed one is kept and the other gains a type
    assert typed == "ci(bots): the smoke proves a tool call (#407)", typed
    assert untyped.startswith("feat: ") and untyped.endswith(" (#407)"), untyped


def test_the_producer_passes_a_body_file_and_no_fixed_title():
    """The Makefile no longer hardcodes the title or the `--wants` placeholder."""

    # Given the open-pr target's recipe
    target = MAKEFILE.split("\nissue-bot-open-pr:", 1)[1].split("\nissue-bot-changed:", 1)[0] \
        if "\nissue-bot-changed:" in MAKEFILE else MAKEFILE.split("\nissue-bot-open-pr:", 1)[1]

    # When  its argv is read
    # Then  it takes the body from a file and carries no fixed title or placeholder
    assert "--body-file" in target, target
    assert "--wants" not in target, target
    assert "issue-bot implementation" not in target, target


def test_the_implement_prompt_asks_for_the_body_before_it_finishes():
    """The agent is told to write the four-part body, so the PR never opens without one."""

    # Given the implementer's prompt
    lines = MAKEFILE.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("_implement-issue:"))
    prompt = "\n".join(l for l in lines[start:start + 6] if l.startswith("\t"))

    # When  its rules are read
    # Then  it names pr-body.md and the four parts
    assert "pr-body.md" in prompt, prompt
    for part in ii.PR_PARTS:
        assert part in prompt, f"{part} is not named in the implementer's prompt"


def test_the_pr_body_is_an_ignored_run_input():
    """pr-body.md is written by the agent and must never be committed as the change."""

    # Given the repository as committed
    # When  git is asked whether the body file is ignored
    ignored = subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", ii.PR_BODY_FILE])

    # Then  it is a run input, like issue.md and triage.md
    assert ignored.returncode == 0, f"{ii.PR_BODY_FILE} is not ignored"
