"""The PR/commit message-substance guard (issue #313) and the closing rule (issue #324).

A commit and a PR are read on their own, so a message that carries a subject and nothing else fails
the reviewer exactly as an empty one does. Every rule is tested on a fixture tree first — a bodiless
commit, a placeholder subject, a subject that is not a typed Conventional Commit, a PR opened with no
body or an empty one, an `AGENTS.md` that lost the mandate or the closing rule, and the Python argv
form the repo's `_gh` helper uses — and then the guard is run over THIS repository, because a
convention the repo itself violates is not a convention.

The exit code matters as much as the rules: `make check-pr-hygiene` runs inside the `ci-unit` job, so
`main(["check"])` must return non-zero on a violation and 0 on this tree.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import check_pr_hygiene as cph  # noqa: E402

#: An AGENTS.md that carries the mandate — the baseline every fixture starts from. It carries BOTH
#: required texts: the message mandate and the closing rule, so a fixture that drops either is the
#: one thing a test breaks.
AGENTS_OK = ("# Agents\n\n" + cph.AGENTS_MANDATE + "\n\n" + cph.AGENTS_CLOSING_RULE
             + "\n\nThe body of the mandate.\n")
#: The three producers whose messages this change gives a body.
PRODUCERS = (".github/workflows/engine-bump.yml",
             ".github/workflows/issue-bot.yml",
             ".github/workflows/registry-sync.yml")


def _tree(tmp_path: Path, shell: str = "", py: str = "", agents: str | None = AGENTS_OK) -> Path:
    """A fixture repo with one shell producer, one Python producer and an AGENTS.md."""
    root = tmp_path / "repo"
    (root / cph.SCRIPTS).mkdir(parents=True, exist_ok=True)
    if shell:
        (root / cph.SCRIPTS / "a.sh").write_text(shell)
    if py:
        (root / cph.SCRIPTS / "a.py").write_text(py)
    if agents is not None:
        (root / cph.AGENTS).write_text(agents)
    return root


def _keys(root: Path) -> list[str]:
    return [f["key"].split("/")[0] for f in cph.findings(root)]


def test_a_bodiless_commit_is_a_violation(tmp_path: Path):
    """A subject with no second message part is a commit a reader cannot learn from."""

    # Given a producer that commits a typed subject and nothing else
    root = _tree(tmp_path, shell='git commit -m "chore(engine): bump x to v1"\n')

    # When  the guard reads it
    keys = _keys(root)

    # Then  the missing body is a violation
    assert "commit-message-body" in keys


def test_a_placeholder_subject_is_a_violation(tmp_path: Path):
    """`-m update -m body` is as empty as `-m update` — the subject says nothing."""

    # Given a producer whose subject is a placeholder
    root = _tree(tmp_path, shell='git commit -m "update" -m "a real body"\n')

    # When  the guard reads it
    keys = _keys(root)

    # Then  the placeholder subject is a violation
    assert "commit-message-placeholder" in keys


def test_a_subject_that_is_not_conventional_is_a_violation(tmp_path: Path):
    """The subject must be a typed Conventional Commit, so history stays machine-readable."""

    # Given a producer whose subject has no type or scope
    root = _tree(tmp_path, shell='git commit -m "bumped things" -m "a real body"\n')

    # When  the guard reads it
    keys = _keys(root)

    # Then  the untyped subject is a violation
    assert "commit-message-subject" in keys


def test_a_subject_and_body_is_accepted(tmp_path: Path):
    """The shape AGENTS.md mandates passes: a typed subject plus a real body."""

    # Given a producer that passes a typed subject and a body variable
    root = _tree(tmp_path, shell='git commit -m "chore(engine): bump x" -m "$msg"\n')

    # When  the guard reads it
    keys = _keys(root)

    # Then  nothing is reported
    assert keys == []


def test_a_commit_with_no_message_at_all_is_a_violation(tmp_path: Path):
    """A commit that passes no `-m` lands empty (or opens an editor that does not exist in CI)."""

    # Given a producer that commits without a message
    root = _tree(tmp_path, shell='git commit --allow-empty\n')

    # When  the guard reads it
    keys = _keys(root)

    # Then  the missing message is a violation
    assert "commit-message" in keys


def test_a_pr_with_no_body_is_a_violation(tmp_path: Path):
    """A PR opened with no `--body` has an empty description a reviewer cannot use."""

    # Given a producer that opens a PR with a title only
    root = _tree(tmp_path, shell='gh pr create --base main --title "chore: thing"\n')

    # When  the guard reads it
    keys = _keys(root)

    # Then  the missing body is a violation
    assert "pr-body-missing" in keys


def test_an_empty_pr_body_is_a_violation(tmp_path: Path):
    """`--body ""` and `--body "-"` are placeholders, not descriptions."""

    # Given a producer that opens a PR with an empty body
    root = _tree(tmp_path,
                 shell='gh pr create --base main --title "chore: thing" --body ""\n'
                       'gh pr create --base main --title "chore: other" --body "-"\n')

    # When  the guard reads it
    keys = _keys(root)

    # Then  both placeholder bodies are violations
    assert keys.count("pr-body-placeholder") == 2


def test_a_body_variable_or_file_is_accepted(tmp_path: Path):
    """A body passed through a variable or a file is a real body — the guard does not read its text."""

    # Given producers that pass a body variable and a body file
    root = _tree(tmp_path,
                 shell='gh pr create --base main --title "chore: thing" --body "$body"\n'
                       'gh pr create --base main --title "chore: other" --body-file body.md\n')

    # When  the guard reads it
    keys = _keys(root)

    # Then  nothing is reported
    assert keys == []


def test_the_python_argv_form_is_covered(tmp_path: Path):
    """The repo's `_gh` helper builds an argv list, so the guard reads that form too."""

    # Given a Python producer that opens a PR without a body
    bad = _tree(tmp_path / "bad", py='out = _gh(gh, ["pr", "create", "--title", title])\n')

    # When  the guard reads it
    bad_keys = _keys(bad)

    # And   a Python producer that passes a body variable
    good = _tree(tmp_path / "good",
                 py='out = _gh(gh, ["pr", "create", "--title", title, "--body", body])\n')

    # Then  the missing body is a violation and the variable is accepted
    assert "pr-body-missing" in bad_keys
    assert _keys(good) == []


def test_a_missing_agents_mandate_is_a_violation(tmp_path: Path):
    """The mandate cannot be deleted silently — its heading is checked."""

    # Given an AGENTS.md without the mandate section
    root = _tree(tmp_path, agents="# Agents\n\nNo mandate here.\n")

    # When  the guard reads it
    keys = _keys(root)

    # Then  the missing mandate is a violation
    assert "agents-mandate" in keys


def test_a_missing_closing_rule_is_a_violation(tmp_path: Path):
    """A PR must close the issue it implements — the closing rule cannot be deleted silently."""

    # Given an AGENTS.md that carries the mandate but NOT the closing rule
    agents = "# Agents\n\n" + cph.AGENTS_MANDATE + "\n\nThe body of the mandate.\n"
    root = _tree(tmp_path, agents=agents)

    # When  the guard reads it
    items = cph.findings(root)
    keys = _keys(root)

    # Then  the closing rule is reported as its OWN finding — not the message mandate
    assert "agents-closing-rule" in keys
    assert "agents-mandate" not in keys
    assert "MUST close it" in cph.render(items)


def test_agents_mandate_passes_when_the_closing_rule_is_present(tmp_path: Path):
    """Both required texts present → no AGENTS.md finding at all."""

    # Given the baseline AGENTS.md, which carries the mandate AND the closing rule
    root = _tree(tmp_path)

    # When  the guard reads it
    keys = _keys(root)

    # Then  neither the mandate nor the closing rule is reported
    assert "agents-mandate" not in keys
    assert "agents-closing-rule" not in keys


def test_this_repository_carries_the_closing_rule():
    """AGENTS.md states the closing rule, so this repo's own PRs follow it."""

    # Given this repository's AGENTS.md
    text = (REPO / cph.AGENTS).read_text()

    # Then  the closing rule text is present, verbatim
    assert cph.AGENTS_CLOSING_RULE in text


def test_check_exits_non_zero_on_a_violation_and_zero_on_this_repo(tmp_path: Path):
    """`main(["check"])` is what `ci-unit` gates on."""

    # Given a fixture tree with a bodiless commit
    root = _tree(tmp_path, shell='git commit -m "chore(engine): bump x"\n')

    # When  the guard checks the fixture and this repository
    bad = cph.main(["check", "--root", str(root)])
    good = cph.main(["check", "--root", str(REPO)])

    # Then  the violation is non-zero and this tree is zero
    assert bad == 1
    assert good == 0


def test_this_repository_passes_its_own_guard():
    """Every producer in this repo passes: a convention the repo violates is not a convention."""

    # Given this repository
    # When  the guard reads it
    items = cph.findings(REPO)

    # Then  it reports no violation
    assert items == [], cph.render(items)


def test_this_repositorys_producers_state_the_issue_the_fix_and_the_benefit():
    """The commit each producer runs carries the three parts and the technical extension."""

    # Given the three producers that commit
    for rel in PRODUCERS:
        text = (REPO / rel).read_text()

        # When  its commit line is read
        commit_lines = [l for l in text.splitlines() if l.strip().startswith("git commit")]

        # Then  it passes a second message part, and the message names all four parts
        assert commit_lines, f"{rel} no longer commits"
        assert all('-m "$msg"' in l for l in commit_lines), rel
        for part in ("Issue:", "Fix:", "Benefit:", "Technical:"):
            assert part in text, f"{rel} does not state {part}"
