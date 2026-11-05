"""`make check-pr-sync-line` refuses a profile-editing bot PR that does not report its live re-sync (issue #1724).

The owner's propagation rule: behaviour-versioned changes (SOUL/skills/rule) land as issues + PRs under
`agents/<profile>/`, and `make sync-agent-profile PROFILE=<p>` is the write path that copies the tree INTO
the live profile. No gate forced that re-sync to be run AND reported — so the tree could hold a new rule
while the live profile that acts under it still runs the old one (#1707 tree-vs-live drift, #1719 a lane
that did not know its own PR merged). This gate reads the PR's diff against `agents/` and, for every
profile dir it touches, requires a `SYNC: <p> make sync-agent-profile PROFILE=<p>` line in the body. These
tests build real commits, because the diff-against-`agents/` read is the thing under test.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_pr_hygiene as hy  # noqa: E402


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


def sync_body() -> str:
    return ("Closes #1724.\n\n"
            "SYNC: llgenie-issse-implementer make sync-agent-profile PROFILE=llgenie-issse-implementer\n\n"
            "Body text.\n")


def test_a_profile_edit_with_the_sync_line_passes(repo: Path):
    commit(repo, "agents/llgenie-issse-implementer/SOUL.md", "new rule\n")
    head = git(repo, "rev-parse", "feature")
    assert hy.sync_line_findings(repo, "feature", "main", sync_body()) == []


def test_a_profile_edit_with_no_sync_line_is_refused_naming_the_profile(repo: Path):
    commit(repo, "agents/llgenie-issse-implementer/SOUL.md", "new rule\n")
    items = hy.sync_line_findings(repo, "feature", "main", "Closes #1724.\n\nBody text.\n")
    assert [i["key"] for i in items] == ["profile-sync"]
    assert "llgenie-issse-implementer" in items[0]["detail"]
    assert "make sync-agent-profile" in items[0]["detail"]


def test_a_sync_line_for_the_wrong_profile_is_refused(repo: Path):
    commit(repo, "agents/llgenie-architect/SOUL.md", "new rule\n")
    items = hy.sync_line_findings(repo, "feature", "main", sync_body())  # names llgenie-issse-implementer
    assert items and "llgenie-architect" in items[0]["detail"]


def test_a_second_profile_edit_needs_a_second_sync_line(repo: Path):
    commit(repo, "agents/llgenie-issse-implementer/SOUL.md", "new rule A\n")
    commit(repo, "agents/llgenie-planner/SOUL.md", "new rule B\n")
    items = hy.sync_line_findings(repo, "feature", "main", sync_body())
    assert items and "llgenie-planner" in items[0]["detail"]


def test_two_sync_lines_two_profiles_passes(repo: Path):
    commit(repo, "agents/llgenie-issse-implementer/SOUL.md", "new rule A\n")
    commit(repo, "agents/llgenie-planner/SOUL.md", "new rule B\n")
    two = ("Closes #1724.\n\n"
           "SYNC: llgenie-issse-implementer make sync-agent-profile PROFILE=llgenie-issse-implementer\n"
           "SYNC: llgenie-planner make sync-agent-profile PROFILE=llgenie-planner\n\n"
           "Body.\n")
    assert hy.sync_line_findings(repo, "feature", "main", two) == []


def test_a_non_profile_change_under_agents_is_skipped(repo: Path):
    # a top-level file (AGENTS.md, agents/standing-rules.md) is not a profile dir — unrelated
    commit(repo, "agents/standing-rules.md", "fleet rule\n")
    assert hy.sync_line_findings(repo, "feature", "main", "Closes #1724.\n\nBody.\n") == []


def test_a_human_only_range_is_skipped_not_failed(repo: Path):
    git(repo, "checkout", "-q", "-b", "human-only", "main")
    commit(repo, "agents/llgenie-issse-implementer/SOUL.md", "rule\n",
           name="Andy", email="andy.holst@protonmail.com")
    assert hy.is_bot_pr(repo, "main", "human-only") is False
    assert hy.pr_sync_line_findings(repo, "human-only", "main", "no sync line, human\n") == []


def test_a_range_with_one_bot_commit_is_gated(repo: Path):
    # human commit besides a bot commit must still be held — `any()` not `all()` (issue #792 shape)
    commit(repo, "agents/llgenie-issse-implementer/SOUL.md", "rule\n",
           name="Andy", email="andy.holst@protonmail.com")
    commit(repo, "agents/llgenie-planner/SOUL.md", "rule\n")  # bot commit
    items = hy.pr_sync_line_findings(repo, "feature", "main", "Closes #1724.\n\nBody.\n")
    assert items, "a mixed range must still be gated"
    assert "llgenie-plan" in items[0]["detail"]


def test_no_diff_under_agents_is_an_empty_pass(repo: Path):
    commit(repo, "scripts/other.py", "x\n")
    assert hy.sync_line_findings(repo, "feature", "main", sync_body()) == []


def test_a_foreign_agents_change_on_main_after_the_base_is_not_attributed(repo: Path):
    """Issue #1754: the sync-line gate passes PR_BASE as the LIVE `origin/main` tip, so a foreign post-base
    `agents/` change that lands on main must NOT read as this PR touching that profile."""
    # the PR itself changes nothing under agents/ — only a scripts file
    commit(repo, "scripts/other.py", "pr change\n")
    # main advances with a foreign agents/ change AFTER the PR's branch point (the live-tip condition)
    git(repo, "checkout", "-q", "main")
    commit(repo, "agents/llgenie-foreign/SOUL.md", "foreign rule\n")
    git(repo, "checkout", "-q", "feature")
    # gate is called with base="main" — a live ref now ahead of the PR's own base
    assert hy.sync_line_findings(repo, "feature", "main", "Closes #1724.\n\nBody.\n") == []


def test_a_same_pr_agents_change_still_demands_sync_after_main_advanced(repo: Path):
    """#1754 fix must not weaken the gate: a genuine same-PR agents/ edit still needs its SYNCh line, and a
    foreign post-base main change beside it is NOT named."""
    commit(repo, "agents/llgenie-issse-implementer/SOUL.md", "rule\n")  # this PR's own profile edit
    git(repo, "checkout", "-q", "main")
    commit(repo, "agents/llgenie-foreign/SOUL.md", "foreign rule\n")  # foreign change after base
    git(repo, "checkout", "-q", "feature")
    items = hy.sync_line_findings(repo, "feature", "main", "Closes #1724.\n\nBody.\n")
    assert items, "a same-PR agents/ edit must still demand its SYNC line"
    assert "llgenie-issse-implementer" in items[0]["detail"]
    assert "llgenie-foreign" not in items[0]["detail"], "a foreign profile must not be misattributed"


def test_the_cli_exits_non_zero_for_a_missing_sync_line(repo: Path, tmp_path: Path):
    commit(repo, "agents/llgenie-security/SOUL.md", "rule\n")
    f = tmp_path / "body.md"
    f.write_text("Closes #1724.\n\nBody.\n")
    rc = hy.main(["sync-line", "--root", str(repo), "--head", "feature", "--base", "main",
                  "--body-file", str(f)])
    assert rc == 1
    f.write_text("Closes #1724.\n\n"
                 "SYNC: llgenie-security make sync-agent-profile PROFILE=llgenie-security\n\nBody.\n")
    assert hy.main(["sync-line", "--root", str(repo), "--head", "feature", "--base", "main",
                    "--body-file", str(f)]) == 0


def test_the_sync_gate_is_wired_into_both_guard_docs_and_full_ci():
    """The #1724 preflight must actually RUN on a PR — not just exist as a subcommand (issue #1675 shape)."""
    for rel in (".github/workflows/ci.yml", ".github/workflows/scope.yml"):
        txt = (REPO / rel).read_text()
        assert "make check-pr-sync-line" in txt, f"{rel} must run the #1724 propagation preflight"
        # it sits right after check-pr-agents-line (which a live-body fetch already precedes) and
        # carries the same live-body env
        step_from = txt.index("make check-pr-agents-line")
        between = txt[step_from:txt.index("make check-pr-sync-line")]
        assert "gh api" in between, rel
        assert "PR_HEAD:" in txt and "PR_BASE: origin/main" in txt, rel
