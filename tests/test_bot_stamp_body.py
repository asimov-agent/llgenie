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
* every bot producer calls it at open — and the roster of who that is is DERIVED from the tree
  (#2110): the python modules whose code carries the `gh pr create` call form (`issue_implementer`,
  `security_bot`, `security_bumps`, `architecture_bot`) and the workflows whose non-comment steps
  run it (`engine-bump.yml`, `registry-sync.yml`, `semgrep-rules-refresh.yml`) — and the fix-bot
  re-stamps a repaired PR and only claims a push when the push step produced a sha.

NO-SKIP POLICY: every case runs the real functions; none is skipped.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

from scripts import bot_preflight as bp
from scripts import check_pr_hygiene as hygiene
from scripts import issue_implementer as ii

from conftest import makefiles_text  # noqa: E402  (the include-resolving Makefile reader)
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


# The derived producer roster (#2110): who opens a bot PR is read off the tree, not remembered.
# A python module is a producer when its CODE carries the call form `"pr", "create"` — prose in a
# docstring never opens a PR. A workflow is a producer when a NON-COMMENT line runs `gh pr create`.
_CALL_FORM = re.compile(r'"pr",\s*"create"')


def _py_pr_openers(scripts_dir: Path) -> list[str]:
    return [p.name for p in sorted(scripts_dir.glob("*.py"))
            if _CALL_FORM.search(p.read_text(encoding="utf-8"))]


def _unstamped_py(scripts_dir: Path) -> list[str]:
    return [name for name in _py_pr_openers(scripts_dir)
            if "bot_preflight.stamp_body" not in (scripts_dir / name).read_text(encoding="utf-8")]


def _unstamped_workflows(workflows_dir: Path) -> list[str]:
    bad: list[str] = []
    for wf in sorted(workflows_dir.glob("*.yml")):
        lines = [ln.strip() for ln in wf.read_text(encoding="utf-8").splitlines()]
        opens = [i for i, ln in enumerate(lines) if "gh pr create" in ln and not ln.startswith("#")]
        if not opens:
            continue
        stamps = [i for i, ln in enumerate(lines) if "make bot-stamp-body" in ln]
        if not stamps or min(stamps) > min(opens):
            bad.append(wf.name)
    return bad


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
    """The producer roster is DERIVED from the tree (#2110), not remembered from a run: every
    module/leg that opens a bot PR is a producer by construction, and every producer stamps."""

    # Given the derived rosters: python modules carrying a real `gh pr create` call-form, and
    # workflows whose NON-COMMENT steps run `gh pr create` (a doc comment is not a producer)
    openers = sorted(_py_pr_openers(REPO / "scripts"))
    assert openers, "the call-form scan found no PR-opener at all — the scan itself broke"
    for name in ("architecture_bot.py", "issue_implementer.py", "security_bot.py",
                 "security_bumps.py"):
        assert name in openers, f"{name} is a producer the derived roster no longer sees"

    # Then every python producer calls the pair authority from a resolved ref — none restates it
    unstamped = _unstamped_py(REPO / "scripts")
    assert unstamped == [], f"unstamped PR producers: {unstamped}"
    for name in openers:
        src = (REPO / "scripts" / name).read_text()
        assert "bot_preflight.resolve_record" in src, f"{name} stamps from an unproven ref"

    # And every opener workflow runs `make bot-stamp-body` before its first `gh pr create`
    bad_wf = _unstamped_workflows(REPO / ".github" / "workflows")
    assert bad_wf == [], f"workflows that open before they stamp: {bad_wf}"
    for name in ("engine-bump.yml", "registry-sync.yml"):
        assert "--body-file /tmp/pr-body.md" in WORKFLOWS[name], f"{name} still passes an unstamped --body"


def test_an_unstamped_new_producer_reds_the_derived_roster(tmp_path):
    """The negative control AC3 names: a NEW module that opens a PR without stamping — or a
    workflow that creates before it stamps — is NAMED by the scan, which is what reddens
    `make test-unit`. A comment that merely mentions `gh pr create` is not a producer."""

    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "issue_implementer.py").write_text(
        'def open_pr(gh):\n'
        '    rec = bot_preflight.resolve_record()\n'
        '    body = bot_preflight.stamp_body(BODY, rec)\n'
        '    return _gh(gh, ["pr", "create", "--repo", "o/r", "--body", body])\n')
    (scripts / "ghost_pr.py").write_text(
        'def open_pr(gh):\n'
        '    return _gh(gh, ["pr", "create", "--repo", "o/r"])\n')
    (scripts / "check_pr_hygiene.py").write_text(
        '"""The gate reads a body. It never opens a PR: `gh pr create` appears only as prose."""\n')
    (scripts / "gh_reader.py").write_text(
        'def view(gh):\n    return _gh(gh, ["pr", "view", "12"])\n')

    assert _py_pr_openers(scripts) == ["ghost_pr.py", "issue_implementer.py"]
    assert _unstamped_py(scripts) == ["ghost_pr.py"]

    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "good.yml").write_text(
        "steps:\n"
        "  - run: make bot-stamp-body BODY=/tmp/pr-body.md\n"
        "  - run: gh pr create --body-file /tmp/pr-body.md\n")
    (workflows / "late.yml").write_text(
        "steps:\n"
        "  - run: gh pr create --body x\n"
        "  - run: make bot-stamp-body BODY=/tmp/pr-body.md\n")
    (workflows / "nostamp.yml").write_text(
        "steps:\n"
        "  - run: gh pr create --body x\n")
    (workflows / "comment-only.yml").write_text(
        "# this leg used to say: gh pr create; today it only reads\n"
        "steps:\n"
        "  - run: gh pr view 12\n")

    assert _unstamped_workflows(workflows) == ["late.yml", "nostamp.yml"]


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
