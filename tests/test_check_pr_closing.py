from __future__ import annotations

import os
import subprocess
from pathlib import Path

from scripts import check_pr_closing as cpc
from scripts.check_pr_closing import main as run_cli

REPO = Path(__file__).resolve().parents[1]

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


# --- the squash text and the PR body close the same claimed issues (issue #1417) ------------


def test_a_claim_without_an_adjacent_close_in_the_squash_text_is_red():
    """A subject `(#N)` is a claim the joined commit text must close."""

    # Given a commit that claims #1417 and a body that does close it
    messages = ["ci(pr): land the gate (#1417)\n\nIssue: #1417\n\nFix: read the messages.\n"]
    body = "closes #1417\n"

    # When the squash check runs
    finding = cpc.check_squash(messages, body, "ci(pr): land the gate (#1417)")

    # Then the squash text is red and names the claim
    assert any(f["key"] == "squash-commit" for f in finding), finding
    assert any("1417" in f["evidence"] for f in finding)


def test_the_body_and_the_squash_text_must_close_the_same_issues():
    """GitHub closes from the body. git log keeps the squash text. The sets match."""

    # Given commits that close #9 and a body that closes #10
    messages = ["ci: land it\n\ncloses #9\n"]
    body = "closes #10\n"

    # When the squash check runs
    finding = cpc.check_squash(messages, body)

    # Then the mismatch is red
    assert any(f["key"] == "squash-mismatch" for f in finding), finding


def test_a_chore_that_claims_nothing_passes():
    """A change that names no issue is not forced to close one."""

    # Given a chore commit and a body with no issue
    messages = ["ci: tidy a comment\n\nFix: drop the stale sentence.\n"]
    body = "No issue. A comment only.\n"

    # When the squash check runs
    finding = cpc.check_squash(messages, body)

    # Then it passes
    assert finding == []


def test_a_prose_mention_is_not_a_claim():
    """A remainder named under Not covered stays open."""

    # Given both texts close #9 and the body also mentions #1413
    messages = ["ci: land it (#9)\n\nIssue: #9\n\ncloses #9\n"]
    body = "closes #9\n\n## Not covered\n\n#1413 stays open.\n"

    # When the squash check runs
    finding = cpc.check_squash(messages, body, "ci: land it (#9)")

    # Then the prose mention is not a claim
    assert finding == []


def test_markdown_between_the_keyword_and_the_ref_is_not_a_squash_close():
    """The #1328 miss applies to the commit text too."""

    # Given a claim closed only as `closes **#9**`
    messages = ["ci: land it (#9)\n\ncloses **#9**\n"]
    body = "closes #9\n"

    # When the squash check runs
    finding = cpc.check_squash(messages, body)

    # Then the squash text is red
    assert any(f["key"] == "squash-commit" for f in finding), finding


def test_an_empty_range_passes():
    """A push to main whose range is empty has nothing to claim."""

    # Given no commits and no body
    # When the squash check runs
    finding = cpc.check_squash([], None)

    # Then it passes
    assert finding == []


def test_the_cli_reads_the_commit_range_git_will_squash(tmp_path):
    """The range is a real `git rev-list`, the same shape the author gate uses."""

    # Given a repository whose only added commit claims #1417 and does not close it
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True, env=os.environ.copy())

    git("init", "-b", "main")
    git("config", "user.email", "andy.holst@protonmail.com")
    git("config", "user.name", "Andy Holst")
    (repo / "README").write_text("base\n")
    git("add", "README")
    git("commit", "-m", "base")
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    (repo / "README").write_text("change\n")
    git("add", "README")
    git("commit", "-m", "ci: land the gate (#1417)\n\nIssue: #1417\n\nFix: read the messages.\n")
    body = tmp_path / "body.md"
    body.write_text("closes #1417\n")

    # When the check reads that range
    code = run_cli([
        "check", "--body-file", str(body), "--base", base, "--rev", "HEAD",
        "--cwd", str(repo), "--title", "ci: land the gate (#1417)",
    ])

    # Then it fails closed
    assert code != 0

    # Given the same range once the commit text also closes #1417
    git("commit", "--amend", "-m",
        "ci: land the gate (#1417)\n\nIssue: #1417\n\nFix: read the messages.\n\ncloses #1417\n")

    # When the check reads it again
    code = run_cli([
        "check", "--body-file", str(body), "--base", base, "--rev", "HEAD",
        "--cwd", str(repo), "--title", "ci: land the gate (#1417)",
    ])

    # Then it passes
    assert code == 0


def _init_repo_with_advancing_main(tmp_path):
    """A repo whose main advanced past a PR's fork point.

    Returns the working paths and shas the live-base tests read:
      (repo, git_env, frozen_base_sha, head_sha, close_msg)
    The PR fork happens at `freeze` (the event base.sha a `pull_request` payload would carry),
    then main advances with its OWN claim (#9) on top, and the PR head is rebased onto that new
    main — so `frozen_base..head` would sweep the main advance into the PR's range (issue #1527).
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True,
                       text=True, env=os.environ.copy())

    def sha(ref="HEAD"):
        return subprocess.check_output(["git", "rev-parse", ref], cwd=repo, text=True).strip()

    git("init", "-b", "main")
    git("config", "user.email", "andy.holst@protonmail.com")
    git("config", "user.name", "Andy Holst")
    (repo / "README").write_text("base\n")
    git("add", "README")
    git("commit", "-m", "chore: base")
    # The PR forks here; this sha is the event payload's frozen base.sha (issue #1527).
    git("checkout", "-b", "feat")
    (repo / "feat.txt").write_text("feat\n")
    git("add", "feat.txt")
    git("commit", "-m", "ci: feat work (#7)\n\nIssue: #7\n\ncloses #7\n")
    frozen_base_sha = sha("HEAD")  # HEAD is now the PR's own commit on `feat`
    # main advances with a commit of its OWN, carrying its own claim (#9).
    git("checkout", "main")
    (repo / "main.txt").write_text("main advance\n")
    git("add", "main.txt")
    git("commit", "-m", "chore: main advance (#9)\n\nIssue: #9\n\ncloses #9\n")
    # The PR head is rebased onto the NEW main, so it now contains main's advance AND has a
    # merge-base with the live origin/main that is *after* the frozen base.sha.
    git("checkout", "feat")
    git("rebase", "main")
    head_sha = sha("HEAD")
    close_msg = "closes #7\n"
    # A local ref named origin/main pointing at the ADVANCED main tip: what a fresh
    # `git fetch origin main` gives the workflow (the live base, not the frozen base.sha).
    git("branch", "origin/main", "main")
    return repo, frozen_base_sha, head_sha, close_msg


def test_a_pr_opened_before_a_main_advance_stays_green(tmp_path):
    """The gate reads the PR's OWN commits, not main's that landed after the event froze its base.

    The event's base.sha predates main's advance. The workflow now passes the LIVE origin/main ref
    and the script anchors the range at `git merge-base origin/main HEAD`, so the range is the PR's
    commit alone — the main-advance claim (#9) is not swept in and the PR stays green (issue #1527).
    """

    # Given a PR whose fork-point base froze before main advanced, rebased onto that newer main
    repo, frozen, head_sha, close_msg = _init_repo_with_advancing_main(tmp_path)
    body = tmp_path / "body.md"
    body.write_text("This change closes the feat.\n\n" + close_msg)

    # When the gate reads the range against the LIVE origin/main ref (what the workflow passes)
    code = run_cli([
        "check", "--body-file", str(body), "--base", "origin/main", "--rev", head_sha,
        "--cwd", str(repo), "--title", "ci: feat work (#7)",
    ])

    # Then a correct PR stays green even though main advanced after it was opened
    assert code == 0, f"live-base run red on a correct PR: base={frozen}..head={head_sha}"

    # And the OLD behavior — base frozen at the event base.sha — swept main's OWN declare (#9) in
    # and red the same PR. Proving the regression the fix removes.
    code_stale = run_cli([
        "check", "--body-file", str(body), "--base", frozen, "--rev", head_sha,
        "--cwd", str(repo), "--title", "ci: feat work (#7)",
    ])
    assert code_stale != 0, "the frozen-base.sha range must still sweep the main advance in"


def test_a_genuine_non_adjacent_claim_still_reds_with_the_live_base(tmp_path):
    """The live base only stops the *sweep* of main's commits; a real unclosed claim stays red."""

    # Given the same repository shape, where the PR's commit claims #7 but never adjacently closes it
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True,
                       text=True, env=os.environ.copy())

    def sha(ref="HEAD"):
        return subprocess.check_output(["git", "rev-parse", ref], cwd=repo, text=True).strip()

    git("init", "-b", "main")
    git("config", "user.email", "andy.holst@protonmail.com")
    git("config", "user.name", "Andy Holst")
    (repo / "README").write_text("base\n")
    git("add", "README")
    git("commit", "-m", "chore: base")
    git("checkout", "-b", "feat")
    (repo / "feat.txt").write_text("feat\n")
    git("add", "feat.txt")
    git("commit", "-m", "ci: feat work (#7)\n\nIssue: #7\n\ncloses **#7**\n")  # non-adjacent: markdown between
    git("checkout", "main")
    (repo / "main.txt").write_text("main advance\n")
    git("add", "main.txt")
    git("commit", "-m", "chore: main advance (#9)\n\nIssue: #9\n\ncloses #9\n")
    git("checkout", "feat")
    git("rebase", "main")
    head_sha = sha("HEAD")
    git("branch", "origin/main", "main")
    body = tmp_path / "body.md"
    body.write_text("closes #7\n")

    # When the gate reads the range against the LIVE origin/main
    code = run_cli([
        "check", "--body-file", str(body), "--base", "origin/main", "--rev", head_sha,
        "--cwd", str(repo), "--title", "ci: feat work (#7)",
    ])

    # Then the genuine non-adjacent claim is still RED — the live base does not disable the gate
    assert code != 0


def _step(text: str, name: str) -> str:
    start = text.index(name)
    rest = text[start:]
    nxt = rest.find("\n      - name:", 1)
    return rest if nxt < 0 else rest[:nxt]


def test_the_unit_job_passes_the_body_into_ci_unit():
    """The unit job writes the event body to a file before make ci-unit."""

    # Given pipeline.yml
    step = _step((REPO / ".github/workflows/pipeline.yml").read_text(), "name: make ci-unit")
    run = step.split("run: |", 1)[1]

    # When the unit step is read
    # Then the run block exports the body path, the env carries PR_BASE, and the run block has no expression
    assert "export PR_BODY=/tmp/pr-body.md" in run
    assert "make ci-unit" in run
    assert "${{" not in run
    assert "PR_BASE:" in step
    assert "PR_BRANCH:" in step


def test_the_make_recipe_passes_the_commit_range():
    """The recipe reads PR_BASE and names the branch PR_BRANCH, not PR_HEAD."""

    # Given the Makefile
    recipe = (REPO / "Makefile").read_text().split("check-pr-closing:", 1)[1].split("\n", 2)[1]

    # When the recipe is read
    # Then it passes the base and the branch variable the author gate does not use as a rev
    assert '--base "$(PR_BASE)"' in recipe
    assert "PR_BRANCH" in recipe
    assert "PR_HEAD" not in recipe


def test_the_guard_and_scope_steps_pass_the_base():
    """Docs pull requests skip linux/unit. Scope and the guard still read the range."""

    # Given the two workflows that already called the gate
    for rel in (".github/workflows/ci.yml", ".github/workflows/scope.yml"):
        step = _step((REPO / rel).read_text(), "name: make check-pr-closing")
        run = step.split("run: |", 1)[1]

        # When the step is read
        # Then it exports the body path and sets PR_BASE, and the run block has no expression
        assert "export PR_BODY=/tmp/pr-body.md" in run, rel
        assert "make check-pr-closing" in run, rel
        assert "${{" not in run, rel
        assert "PR_BASE:" in step, rel


def test_check_pr_closing_stays_deferred():
    """The body still does not exist before the pull request event."""

    # Given the issue-bot gate table
    from scripts import issue_bot_gates

    # When the closing gate is classified
    reason = issue_bot_gates.DEFERRED["check-pr-closing"]

    # Then it stays deferred and the reason names the commit text
    assert "check-pr-closing" not in issue_bot_gates.FAST_GATES
    assert "commit" in reason
    assert "body" in reason
