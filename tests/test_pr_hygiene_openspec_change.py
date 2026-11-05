"""`make check-pr-openspec-change` refuses an implementing bot PR that adds no OpenSpec change (issue #1807).

`ci-openspec` (openspec-validate-all + openspec-tasks-check) only iterates EXISTING changes under
`openspec/changes/*`, so an implementing PR that adds no change dir is structurally invisible and
CI-green. AGENTS.md (lines 27-53, MANDATORY) requires every change to start as an OpenSpec change created
before the branch. This gate closes the PRESENCE half: a bot implementing PR's final diff must add a file
under `openspec/changes/`, or the body must name an ACTIVE change it implements against (`OPENSPEC: <name>`),
or the PR must be pure docs/regen (nothing to spec-track). It never re-validates structure/ticks — the two
existing openspec gates own those (no weakening). These tests build real commits, because the diff read
(does the range add an openspec/ file?) is the thing under test.
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


def commit(root: Path, rel: str, body: str, name: str = "Asimov Agent", email: str = "support@docondee.com") -> str:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    git(root, "add", "-A")
    git(root, "-c", f"user.name={name}", "-c", f"user.email={email}", "commit", "-q", "-m", f"work on {rel}")
    return git(root, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    commit(root, "a.txt", "base\n")
    git(root, "checkout", "-q", "-b", "feature")
    return root


def plain_body() -> str:
    return "Closes #1807.\n\nBody text.\n"


def test_an_openspec_empty_implementing_pr_is_refused(repo: Path):
    # product code (scripts + tests) with no openspec/ at all — the #1806 failing shape
    commit(repo, "scripts/issue_refiner.py", "def refine(): pass\n")
    commit(repo, "tests/test_issue_refiner.py", "def test_refine():\n    pass\n")
    items = hy.openspec_change_findings(repo, "feature", "main", plain_body())
    assert [i["key"] for i in items] == ["openspec-change"]
    assert "openspec" in items[0]["detail"].lower()
    assert "make openspec-new" in items[0]["detail"]


def test_a_pr_that_adds_its_own_change_passes(repo: Path):
    commit(repo, "openspec/changes/some-change/tasks.md", "# Tasks\n- [x] 1. done\n")
    commit(repo, "scripts/impl.py", "def x():\n    pass\n")
    assert hy.openspec_change_findings(repo, "feature", "main", plain_body()) == []


def test_an_archived_change_alone_is_refused(repo: Path):
    # a change under openspec/changes/archive/ is not an active change the PR implements — still empty
    commit(repo, "openspec/changes/archive/old/tasks.md", "# Tasks\n- [x] 1. done\n")
    commit(repo, "scripts/impl.py", "def x():\n    pass\n")
    items = hy.openspec_change_findings(repo, "feature", "main", plain_body())
    assert items, "an archived-only openspec/ diff must NOT exempt the PR"
    assert items[0]["key"] == "openspec-change"


def test_a_body_named_existing_change_exempts(repo: Path):
    # an ACTIVE change exists in the tree; the body names it via OPENSPEC:
    commit(repo, "openspec/changes/topic-driven/tasks.md", "# Tasks\n- [x] 1. done\n")
    body = "Closes #1807.\n\nOPENSPEC: topic-driven\n\nImplements against the existing topic-driven change.\n"
    assert hy.openspec_change_findings(repo, "feature", "main", body) == []


def test_a_body_line_naming_a_missing_change_is_refused(repo: Path):
    # OPENSPEC: names a change that does NOT exist on the tree — the exemption is only for an ACTIVE change
    commit(repo, "scripts/impl.py", "def x():\n    pass\n")
    body = "Closes #1807.\n\nOPENSPEC: does-not-exist\n\n"
    assert hy.openspec_change_findings(repo, "feature", "main", body)


def test_a_pure_docs_pr_is_exempt(repo: Path):
    # docs/regen/change-note trio only — nothing product to spec-track
    commit(repo, "docs/changes.d/2026-11-05-note.md", "| row |\n")
    commit(repo, "CHANGES.md", "| 2026-11-05 | note |\n")
    assert hy.openspec_change_findings(repo, "feature", "main", plain_body()) == []


def test_a_human_only_range_is_skipped(repo: Path):
    git(repo, "checkout", "-q", "-b", "human-only", "main")
    commit(repo, "scripts/human.py", "def h():\n    pass\n",
           name="Andy", email="andy.holst@protonmail.com")
    assert hy.is_bot_pr(repo, "main", "human-only") is False
    assert hy.pr_openspec_change_findings(repo, "human-only", "main", plain_body()) == []


def test_a_range_with_one_bot_commit_is_gated(repo: Path):
    # human commit beside a bot commit must still be held — any() not all() (issue #792 shape)
    commit(repo, "scripts/human.py", "def h():\n    pass\n",
           name="Andy", email="andy.holst@protonmail.com")
    commit(repo, "tests/test_impl.py", "def test_i():\n    pass\n")  # bot commit
    items = hy.pr_openspec_change_findings(repo, "feature", "main", plain_body())
    assert items, "a mixed range must still be gated"
    assert items[0]["key"] == "openspec-change"


def test_no_product_diff_is_an_empty_pass(repo: Path):
    commit(repo, "docs/notes.md", "# notes\n")
    assert hy.openspec_change_findings(repo, "feature", "main", plain_body()) == []


def test_this_very_change_would_pass_its_own_gate(repo: Path):
    # the introducing change carries its own openspec/changes/openspec-presence-gate/ — so this PR (#1807)
    # literally proves red-on-old/green-on-fixed: the empty implementing PR above fails, this one passes.
    commit(repo, "openspec/changes/openspec-presence-gate/tasks.md", "# Tasks\n- [x] 1. done\n")
    commit(repo, "openspec/changes/openspec-presence-gate/proposal.md", "# proposal\n")
    commit(repo, "scripts/check_pr_hygiene.py", "def openspec_change_findings():\n    return []\n")
    assert hy.openspec_change_findings(repo, "feature", "main", plain_body()) == []


def test_the_cli_exits_non_zero_for_a_missing_openspec_change(repo: Path, tmp_path: Path):
    commit(repo, "scripts/impl.py", "def x():\n    pass\n")
    f = tmp_path / "body.md"
    f.write_text(plain_body())
    rc = hy.main(["openspec-change", "--root", str(repo), "--head", "feature", "--base", "main",
                  "--body-file", str(f)])
    assert rc == 1
    # now the body names an existing active change, or we add the change itself — the CLI goes green
    f.write_text("Closes #1807.\n\nOPENSPEC: tree-change\n\n")
    commit(repo, "openspec/changes/tree-change/tasks.md", "# Tasks\n- [x] 1. done\n")
    assert hy.main(["openspec-change", "--root", str(repo), "--head", "feature", "--base", "main",
                    "--body-file", str(f)]) == 0


def test_the_openspec_gate_is_wired_into_both_guard_docs_and_full_ci():
    """The #1807 presence gate must actually RUN on a PR — not just exist as a subcommand."""
    for rel in (".github/workflows/ci.yml", ".github/workflows/scope.yml"):
        txt = (REPO / rel).read_text()
        assert "make check-pr-openspec-change" in txt, f"{rel} must run the #1807 OpenSpec-presence preflight"
        # it sits beside check-pr-sync-line and carries the same live-body env
        step_from = txt.index("make check-pr-sync-line")
        between = txt[step_from:txt.index("make check-pr-openspec-change")]
        assert "gh api" in between, rel
        assert "PR_HEAD:" in txt and "PR_BASE: origin/main" in txt, rel
