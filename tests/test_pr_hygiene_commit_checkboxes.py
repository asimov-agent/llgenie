"""`make check-pr-commit-checkboxes` refuses commit text that lacks the ticked acceptance mirror (issue #2519).

PR #2509 was auto-merged as squash `49f0cc3be` whose commit text carries `checked=0 unchecked=3`
(`git show 49f0cc3be -s --format=%B`): the issue/PR-body pair was already locked by #2511, but the
commit message — the PERMANENT record a squash lands on main — was read by nothing. These tests
build real bot commits, because the commit range is the thing under test.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

from scripts import auto_merge as am  # noqa: E402
from scripts import check_pr_hygiene as hy  # noqa: E402
import gh_fake  # noqa: E402  (the shared fake-gh field guard, issue #2975)

BOT = ("Asimov Agent", "support@docondee.com")


def git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def commit(root: Path, name: str, message: str, author: tuple[str, str] = BOT) -> str:
    (root / name).write_text(name)
    git(root, "add", "-A")
    git(root, "-c", f"user.name={author[0]}", "-c", f"user.email={author[1]}",
        "commit", "-q", "-m", message)
    return git(root, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    commit(root, "a.txt", "base", author=("Andy", "andy.holst@protonmail.com"))
    git(root, "checkout", "-q", "-b", "feature")
    return root


# The exact #2509 shape: the bot pasted the issue's UNTICKED checklist into its commit message.
UNTICKED_MSG = (
    "feat(x): the change (issue #2519)\n\n"
    "## Acceptance criteria\n"
    "- [ ] gate refuses unticked commit text\n"
    "- [ ] merge lane defers on unticked commit text\n"
    "- [ ] wiring green in CI\n"
)

TICKED_MSG = (
    "feat(x): the change (issue #2519)\n\n"
    "Acceptance:\n"
    "- [x] gate refuses unticked commit text (proven: pytest rc=0 deadbeef)\n"
    "- [x] merge lane defers on unticked commit text (proven: pytest rc=0 deadbeef)\n"
    "- [x] wiring green in CI (proven: run=1 rc=0)\n"
)

BODY_WITH_CRITERIA = (
    "## Problem\nthe squash landed unticked boxes\n\n"
    "## Acceptance criteria\n"
    "- [ ] gate refuses unticked commit text\n"
    "- [ ] merge lane defers on unticked commit text\n"
    "- [ ] wiring green in CI\n\n"
    "## Technical\nscripts/check_pr_hygiene.py\n"
)


def test_unticked_acceptance_boxes_in_commit_text_are_refused(repo: Path):
    """The #2509 shape, caught before merge instead of inside `49f0cc3be` on main."""
    commit(repo, "b.txt", UNTICKED_MSG)
    items = hy.commit_checkboxes_findings(repo, "feature", "main", "")
    assert [i["key"] for i in items] == ["commit-unchecked-acceptance"]
    assert "3 unticked" in items[0]["detail"]


def test_tick_mirror_satisfies_the_gate(repo: Path):
    commit(repo, "b.txt", TICKED_MSG)
    assert hy.commit_checkboxes_findings(repo, "feature", "main", BODY_WITH_CRITERIA) == []


def test_declared_criteria_without_a_commit_mirror_are_refused(repo: Path):
    """The tick happened on the body but never reached the permanent record."""
    commit(repo, "b.txt", "feat(x): the change (issue #2519)\n\nno checklist here at all\n")
    items = hy.commit_checkboxes_findings(repo, "feature", "main", BODY_WITH_CRITERIA)
    assert [i["key"] for i in items] == ["commit-acceptance-unmirrored"]
    assert "3 acceptance items" in items[0]["detail"] and "0 ticked" in items[0]["detail"]


def test_a_partially_ticked_commit_text_still_lags(repo: Path):
    commit(repo, "b.txt", "feat(x): x\n\nAcceptance:\n- [x] one\n")
    items = hy.commit_checkboxes_findings(repo, "feature", "main", BODY_WITH_CRITERIA)
    assert [i["key"] for i in items] == ["commit-acceptance-unmirrored"]


def test_unticked_boxes_outside_an_acceptance_heading_are_not_this_gates_business(repo: Path):
    """Scope: an acceptance heading, not any `- [ ]` anywhere in prose."""
    commit(repo, "b.txt", "docs(x): quote\n\nthe sample shows:\n- [ ] an example line, not acceptance\n")
    assert hy.commit_checkboxes_findings(repo, "feature", "main", "") == []


def test_a_human_only_range_is_skipped_not_failed(repo: Path):
    commit(repo, "h.txt", UNTICKED_MSG, author=("Andy", "andy.holst@protonmail.com"))
    assert hy.is_bot_pr(repo, "main", "feature") is False
    assert hy.commit_checkboxes_findings(repo, "feature", "main", BODY_WITH_CRITERIA) == []


def test_the_cli_exits_non_zero_for_unticked_commit_text(repo: Path, tmp_path: Path):
    commit(repo, "b.txt", UNTICKED_MSG)
    rc = hy.main(["commit-checkboxes", "--root", str(repo), "--head", "feature", "--base", "main"])
    assert rc == 1
    # The amend rewrites the COMMITTER too — an identity-less amend dies with 128 in a container
    # that has no global git identity, exactly the environment the real merge lane runs in.
    git(repo, "-c", f"user.name={BOT[0]}", "-c", f"user.email={BOT[1]}",
        "commit", "-q", "--amend", "-m", TICKED_MSG)
    f = tmp_path / "body.md"
    f.write_text(BODY_WITH_CRITERIA)
    assert hy.main(["commit-checkboxes", "--root", str(repo), "--head", "feature", "--base", "main",
                    "--body-file", str(f)]) == 0


def test_the_merge_lane_defers_a_pr_whose_commits_lack_the_mirror(repo: Path, monkeypatch):
    """`auto_merge.decide()` refuses to reach `gh pr merge` while the live commits carry unticked
    acceptance boxes: the hold is a deferral reason (exit 0), never a red run and never a merge."""
    commit(repo, "b.txt", UNTICKED_MSG)
    msgs = git(repo, "log", "--no-merges", "--format=%B%x00", "main..feature")

    def fake_gh(gh, args, token=""):
        gh_fake.enforce(list(args))   # issue #2975: the shim answers only field names real gh has
        if args[0] == "api":                      # pulls/<n>/commits --paginate
            return msgs
        return BODY_WITH_CRITERIA                 # pr view --json body

    monkeypatch.setattr(am, "_gh", fake_gh)
    reason = am.commit_checkbox_hold("gh", "o/r", 1)
    assert reason and "commit-unchecked-acceptance" in reason

    git(repo, "-c", f"user.name={BOT[0]}", "-c", f"user.email={BOT[1]}",
        "commit", "-q", "--amend", "-m", TICKED_MSG)
    msgs = git(repo, "log", "--no-merges", "--format=%B%x00", "main..feature")
    assert am.commit_checkbox_hold("gh", "o/r", 1) is None


# ---------------------------------------------------------------------------
# fake-gh field refusal (issue #2975): the shim dies like real gh on the #513 field
# ---------------------------------------------------------------------------
def test_the_legs_gh_shim_refuses_the_513_author_association_request(repo: Path, monkeypatch):
    commit(repo, "b.txt", UNTICKED_MSG)
    msgs = git(repo, "log", "--no-merges", "--format=%B%x00", "main..feature")

    def fake_gh(gh, args, token=""):
        gh_fake.enforce(list(args))
        if args[0] == "api":
            return msgs
        return BODY_WITH_CRITERIA

    monkeypatch.setattr(am, "_gh", fake_gh)
    with pytest.raises(SystemExit) as boom:
        am._gh("gh", ["pr", "view", "1", "--repo", "o/r", "--json", "authorAssociation"])
    assert boom.value.code == 1
    assert am.commit_checkbox_hold("gh", "o/r", 1)  # the leg still sees its own reads refused


# ---------------------------------------------------------------------------
# commit-tick-draft-stub: a `(proven: …)` clause with an un-replaced draft stub is refused (#3075)
# ---------------------------------------------------------------------------
# The measured #3035 residue that LANDED (`main@53a56da90`): three proven clauses carrying an
# un-replaced draft stub — two blob-sha clauses whose 40-hex blob token satisfied the rc+sha rule
# and one engine-build clause — all rode the squash onto main as the permanent record.

STUB_MSG = (
    "feat(engine-sync): pins (issue #3075)\n\n"
    "Acceptance:\n"
    "- [x] the pins moved (proven: gh api repos/asimov-agent/llgenie/git/blobs/"
    "fe0022448ccf022359c20805f02d58ad10fbb130 rc=0 PLACEHOLDER)\n"
    "- [x] the images retagged (proven: gh api repos/asimov-agent/llgenie/git/blobs/"
    "a11ce75b2c955f5c077f8935588010187295199d rc=0 PLACEHOLDER)\n"
    "- [x] engine-build proved it (proven: rc=0, engine-build run at head PLACEHOLDER)\n"
)

CLEAN_MSG = (
    "feat(engine-sync): pins (issue #3075)\n\n"
    "Acceptance:\n"
    "- [x] the pins moved (proven: make check-engine-pins rc=0 at head 53a56da9)\n"
    "- [x] the images retagged (proven: make test-published-engine rc=0 at head 53a56da9)\n"
    "- [x] engine-build proved it (proven: run=45750923126 at head 53a56da9)\n"
)


def test_draft_stub_proven_clauses_in_commit_text_are_refused(repo: Path):
    """The exact #3035 squash shape, caught before merge instead of inside `53a56da90` on main."""
    commit(repo, "b.txt", STUB_MSG)
    items = hy.commit_checkboxes_findings(repo, "feature", "main", "")
    assert [i["key"] for i in items] == ["commit-tick-draft-stub"], [i["key"] for i in items]
    assert "3 `(proven: …)` clause(s)" in items[0]["detail"]


def test_the_same_commit_text_with_real_proof_passes(repo: Path):
    """The refusal is stub-specific: identical checklist shape, clauses naming real proof, stays green."""
    commit(repo, "b.txt", CLEAN_MSG)
    assert hy.commit_checkboxes_findings(repo, "feature", "main", "") == []


def test_prose_naming_the_stub_word_without_a_proven_clause_is_not_flagged(repo: Path):
    """Scope: a `(proven: …)` clause carrying the stub, not any mention of the word (#3075)."""
    commit(repo, "b.txt", "docs(x): note\n\nAcceptance:\n"
           "- [x] gate refuses the stub (proven: pytest tests rc=0 at head 53a56da9)\n\n"
           "the residue this gate hunts is the word PLACEHOLDER inside a proof clause.\n")
    assert hy.commit_checkboxes_findings(repo, "feature", "main", "") == []


def test_the_merge_lane_defers_commits_whose_proofs_carry_the_stub(repo: Path, monkeypatch):
    """`auto_merge.decide()` treats a stub-carrying tick as a deferral reason (exit 0), never a merge."""
    commit(repo, "b.txt", STUB_MSG)

    def fake_gh(gh, args, token=""):
        gh_fake.enforce(list(args))
        if args[0] == "api":
            return git(repo, "log", "--no-merges", "--format=%B%x00", "main..feature")
        return ""

    monkeypatch.setattr(am, "_gh", fake_gh)
    reason = am.commit_checkbox_hold("gh", "o/r", 1)
    assert reason and "commit-tick-draft-stub" in reason
