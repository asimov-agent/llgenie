#!/usr/bin/env python3
"""A bot PR carries the `AGENTS:`/`BASE:` pair at OPEN, written by the seam that opens it (#2050).

Measured 2026-11-07: five bot PRs (#1696, #1982, #2039, #2043, #2049) were red on
`make check-pr-agents-line` because the body never carried a valid pair — the stamp was a step a leg
had to REMEMBER (`make bot-preflight`), and no producer wrote it. A repair pass did not re-write it
either, and the fix-bot's own comment claimed a push on #2051 whose head never moved.

So this file locks the two halves of the fix:

* `bot_preflight.stamp_body` is the ONE stamper: it inserts or REPLACES the pair, flush-left, and the
  result passes the gate's own `agents_line_findings` — proven against a real git repository, with the
  unstamped body as the negative control;
* every bot producer calls it at open — the issue-bot's `render_pr_body`, `engine-bump.yml`,
  `registry-sync.yml`, `security_bot`, `security_bumps` — and the fix-bot re-stamps a repaired PR and
  only claims a push when the push step produced a sha.

NO-SKIP POLICY: every case runs the real functions; none is skipped.
"""
from __future__ import annotations


from conftest import makefiles_text
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

from scripts import bot_preflight as bp
from scripts import check_pr_hygiene as hygiene
from scripts import issue_implementer as ii

MAKEFILE = makefiles_text()
WORKFLOWS = {p.name: p.read_text() for p in (REPO / ".github" / "workflows").glob("*.yml")}

RECORD = {
    "main": "cb6c56a955124d58818d595bca34c4d60745c0ab",
    "agents_bytes": 91766,
    "agents_lines": 1363,
    "agents_headings": 42,
    "agents_headings_sha256": "0" * 64,
}


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def _bot_repo(tmp_path: Path, agents: str = "# Rules\r\n\r\n## Problem\r\n") -> Path:
    """A real repository whose commits are authored by a bot identity, so `is_bot_pr` is true."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Asimov Agent")
    _git(repo, "config", "user.email", "support@docondee.com")
    (repo / "AGENTS.md").write_text(agents)
    _git(repo, "add", "AGENTS.md")
    _git(repo, "commit", "-m", "chore: main")
    _git(repo, "checkout", "-b", "feat")
    (repo / "work.txt").write_text("x\n")
    _git(repo, "add", "work.txt")
    _git(repo, "commit", "-m", "feat: work")
    return repo


def test_the_stamp_is_flush_left_at_the_end_and_beside_itself():
    """The pair is appended flush-left, AGENTS directly above BASE — the shape the gate matches."""

    # Given a producer's body with prose only
    body = "Issue: #11 — x\n\nFix: y\n\nBenefit: z\n\nTechnical: scripts/x.py\n"

    # When  it is stamped
    stamped = bp.stamp_body(body, RECORD)

    # Then  both lines are present, unindented, adjacent, and the prose is untouched
    lines = stamped.splitlines()
    assert bp.agents_line(RECORD) in lines
    assert lines.index(bp.base_line(RECORD)) == lines.index(bp.agents_line(RECORD)) + 1
    assert stamped.startswith("Issue: #11 — x\n\nFix: y")
    assert stamped.endswith("\n")


def test_a_stale_or_mangled_pair_is_replaced_not_duplicated():
    """A body a previous pass got wrong is repaired: one pair survives, the measured one."""

    # Given a body carrying an old valid pair AND a mangled prose line
    stale = (f"AGENTS: {'a' * 40} 1b 1l\nBASE: {'a' * 40} (== origin/main at open)\n"
             "AGENTS: some prose about the rulebook\n\nIssue: #11 — x\n")

    # When  it is re-stamped
    stamped = bp.stamp_body(stale, RECORD)

    # Then  exactly one AGENTS line and one BASE line remain, both the measured ones
    assert stamped.count("AGENTS:") == 1, stamped
    assert stamped.count("BASE:") == 1, stamped
    assert bp.agents_line(RECORD) in stamped and bp.base_line(RECORD) in stamped


def test_stamping_is_idempotent():
    """A second pass over an already-stamped body changes nothing (fix-bot re-runs it)."""
    once = bp.stamp_body("Issue: #11 — x\n", RECORD)
    assert bp.stamp_body(once, RECORD) == once


def test_a_stamped_body_passes_the_gate_and_the_unstamped_one_does_not(tmp_path):
    """The gate's own function is the judge: unstamped RED, stamped GREEN, same tree and head."""

    # Given a real bot-authored branch off main
    repo = _bot_repo(tmp_path)

    # When  the rulebook is measured at main and a body is stamped from it
    record = bp.rulebook(repo, "main")
    body = bp.stamp_body("Issue: #11 — x\n\nFix: y\n\nBenefit: z\n\nTechnical: t\n", record)

    # Then  the gate accepts the stamped body…
    assert hygiene.pr_agents_line_findings(repo, "HEAD", "main", body) == []
    # …and the SAME body without the pair is red (the negative control for this guard)
    findings = hygiene.pr_agents_line_findings(
        repo, "HEAD", "main", "Issue: #11 — x\n\nFix: y\n\nBenefit: z\n\nTechnical: t\n")
    assert [f["key"] for f in findings] == ["agents-line"], findings


def test_the_record_is_measured_from_the_ref_the_checkout_stands_on(tmp_path):
    """`resolve_record` refuses rather than stamping from a ref it cannot prove is main."""

    # Given a real repo whose main is reachable as `main`
    repo = _bot_repo(tmp_path)

    # When  it resolves with a fallback list that names it
    record = bp.resolve_record(repo, "origin/main", ("origin/HEAD", "main"))

    # Then  the record names this repo's main commit
    assert record["main"] == _git(repo, "rev-parse", "main")

    # And when no ref resolves at all, it refuses (never an unmeasurable stamp)
    with pytest.raises(bp.PreflightError) as refused:
        bp.resolve_record(repo, "origin/main", ("origin/HEAD", "upstream/main"))
    assert "issue #2050" in str(refused.value)


def test_the_issue_bot_body_carries_the_pair_at_open():
    """`render_pr_body` is the issue-bot's PR body: the pair is written there, not left to a leg."""

    # Given a complete four-part body
    good = ("Issue: #11 — x\n\nFix: y\n\nBenefit: z\n\nTechnical: scripts/x.py\n")

    # When  it is rendered for the PR
    body = ii.render_pr_body(good, 11, " scripts/x.py | 1 +", RECORD)

    # Then  it carries the measured pair, beside itself, and still closes the issue
    assert bp.agents_line(RECORD) in body.splitlines()
    assert bp.base_line(RECORD) in body.splitlines()
    assert "closes #11" in body


def test_open_pr_refuses_to_open_a_body_it_cannot_stamp(tmp_path, monkeypatch):
    """A leg that cannot measure main fails LOUDLY instead of opening an unstamped bot PR."""

    # Given a leg with a body but a checkout where no main ref resolves
    body_file = tmp_path / ii.PR_BODY_FILE
    body_file.write_text("Issue: #11 — x\n\nFix: y\n\nBenefit: z\n\nTechnical: t\n")

    def boom(*a, **k):
        raise ii.bot_preflight.PreflightError("no ref to measure the rulebook at (tried origin/main)")

    # `scripts.bot_preflight` and the producer's bare `bot_preflight` are two module objects (the
    # suite's two import roots), so the refusal is planted on the module the PRODUCER calls.
    monkeypatch.setattr(ii.bot_preflight, "resolve_record", boom)
    monkeypatch.setattr(ii, "_gh", lambda gh, args, token=None: "https://x.invalid/pull/9")

    # When  it tries to open the PR
    with pytest.raises(SystemExit) as refused:
        ii.open_pr("gh", "o/r", 11, "agent/issue-11-s", "fix(x): t", str(body_file))

    # Then  the refusal names the missing stamp and no PR is opened
    assert "#2050" in str(refused.value), refused.value


def test_every_bot_pr_producer_stamps_before_it_opens_or_edits():
    """The producers that open/edit a bot PR call the ONE stamper before the `gh pr` write."""

    # Given the workflow producers that create or edit a bot PR body in shell
    for name in ("engine-bump.yml", "registry-sync.yml"):
        text = WORKFLOWS[name]
        assert "make bot-stamp-body" in text, f"{name} opens a PR body without stamping it"
        assert text.index("make bot-stamp-body") < text.index("gh pr create"), \
            f"{name} stamps AFTER it opens the PR"
        assert "--body-file /tmp/pr-body.md" in text, f"{name} still passes an unstamped --body"

    # And the python producers call the same pair authority, not a restated copy
    for module in ("issue_implementer.py", "security_bot.py", "security_bumps.py"):
        src = (REPO / "scripts" / module).read_text()
        assert "bot_preflight.stamp_body" in src, f"{module} composes a bot PR body without stamping"
        assert "bot_preflight.resolve_record" in src, f"{module} stamps from an unproven ref"


def test_the_fix_bot_re_stamps_a_repair_and_only_claims_a_push_it_made():
    """The repair pass must (a) re-stamp the body it repaired and (b) never claim a phantom push."""

    # Given the fix-bot workflow
    text = WORKFLOWS["fix-bot.yml"]

    # Then  a re-stamp step runs after the push, gated on the push having produced a sha
    assert "make bot-stamp-body" in text, "#2050: a repair leaves the body unstamped"
    assert "steps.push.outputs.pushed != ''" in text, "the re-stamp is not gated on a real push"

    # And the outcome comment reads the push step's output instead of the loop's verdict alone
    assert "PUSHED: ${{ steps.push.outputs.pushed }}" in text, \
        "the comment cannot tell a push from a no-op green loop (#2051's false-push claim)"
    assert '[ -n "${PUSHED:-}" ]' in text, "the comment still claims a push on a green no-op"


def test_fix_bot_claims_a_push_only_when_the_api_head_ref_moved():
    """#2370: 'Pushed as one commit' is bounded by the PR head ref READ BACK from the API differing
    between before and after the repair — a green loop verdict is never the fact by itself."""

    # Given the fix-bot workflow
    text = WORKFLOWS["fix-bot.yml"]

    # Then  it captures a pre-push baseline headRefOid from the PR API before the loop
    assert 'gh pr view "$NUM" --repo "${{ github.repository }}" --json headRefOid -q .headRefOid' in text, \
        "#2370: the pre-push baseline must be read from the PR API (headRefOid)"
    assert "id: prehead" in text, "#2370: the pre-push head-ref capture step is missing"

    # And it reads the post-push headRefOid back from the API after the push step
    assert "id: posthead" in text, "#2370: the post-push head-ref read-back step is missing"

    # And the comment step compares PRE and POST, claiming a push only when they differ
    assert "PRE: ${{ steps.prehead.outputs.head }}" in text, "#2370: PRE is not wired to the comment"
    assert "POST: ${{ steps.posthead.outputs.head }}" in text, "#2370: POST is not wired to the comment"
    assert '$POST" != "${PRE:-}"' in text, "#2370: the push claim is not gated on the API ref having moved"
    assert "the PR head ref did not move (pre" in text, \
        "#2370: a no-move head must post a non-success comment naming the unchanged head"


def test_the_stamp_target_is_wired_and_documented():
    """`make bot-stamp-body` exists, is phony, and is the documented pre-open step (#2050)."""

    # Given the make target every producer calls
    assert "\nbot-stamp-body:" in MAKEFILE
    assert ".PHONY: bot-stamp-body" in MAKEFILE, "a target that writes no file of its own name must be phony (#392)"

    # Then  it documents its usage refusal and the two knobs a checkout needs
    recipe = MAKEFILE.split("\nbot-stamp-body:", 1)[1].split("\n\n", 1)[0]
    assert "BODY=" in recipe and "--stamp" in recipe
    assert "BASE" in recipe and "REFS" in recipe
