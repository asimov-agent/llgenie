#!/usr/bin/env python3
"""The head-repository report: a cross-repo PR is explained, never silently accepted (issue #910).

Agents push to `asimov-agent/llgenie`; a PR whose head is a fork costs the repository its secrets on the
`pull_request` event and its own approval semantics. The check is a WARNING with a reason — the existing
cross-repository PRs are legitimate — so these tests pin two things: that a fork head is NAMED, and that the
check does not turn that into a failure unless a caller explicitly asks for it with `--strict`.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import pr_heads  # noqa: E402  (the real module, never a copy)


def pr(number: int, author: str, cross: bool, head_owner: str = "asimov-agent") -> dict:
    return {"number": number, "title": f"PR {number}", "author": {"login": author},
            "headRepositoryOwner": {"login": head_owner}, "isCrossRepository": cross,
            "headRefName": f"branch-{number}"}


def run(tmp_path: Path, prs: list[dict], *args: str) -> subprocess.CompletedProcess:
    """Drive the real CLI with a stubbed `gh` that answers `pr list` with this fixture."""
    listing = json.dumps(prs)
    gh = tmp_path / "gh"
    gh.write_text("#!/bin/sh\ncat <<'JSON'\n" + listing + "\nJSON\n", encoding="utf-8")
    gh.chmod(0o755)
    return subprocess.run([sys.executable, str(REPO / "scripts" / "pr_heads.py"), *args, "--gh", str(gh)],
                          capture_output=True, text=True)


def test_a_fork_head_is_reported_with_its_reason_and_remedy(tmp_path):
    """The negative control #910 asks for: a deliberate fork-head PR is NAMED, not silently accepted."""
    result = run(tmp_path, [pr(1, "andyholst", False), pr(2, "agent", True, "andyholst")], "report")

    assert result.returncode == 0, result.stderr
    assert "#2" in result.stdout, result.stdout
    assert "CROSS-REPOSITORY" in result.stdout
    assert "no repository secrets" in result.stdout, "the reason must be stated, not implied"
    assert "push the branch to asimov-agent/llgenie" in result.stdout, "the remedy must be concrete"


def test_a_same_repo_pr_is_not_flagged(tmp_path):
    """The ordinary path stays quiet: a report that warns about everything warns about nothing."""
    result = run(tmp_path, [pr(1, "andyholst", False)], "report")

    assert result.returncode == 0, result.stderr
    assert "#1" not in result.stdout, result.stdout
    assert "CROSS-REPOSITORY" in result.stdout           # the count line always prints …
    assert "0 CROSS-REPOSITORY" in result.stdout         # … and it says zero when there are none


def test_check_warns_without_failing_because_the_existing_prs_are_legitimate(tmp_path):
    """15 cross-repository PRs are open today; failing on them would teach the next person to skip it."""
    result = run(tmp_path, [pr(2, "agent", True, "andyholst")], "check")

    assert result.returncode == 0, result.stderr
    assert "#2" in result.stdout and "cross-repository heads" in result.stdout


def test_strict_turns_the_warning_into_a_failure_when_a_caller_asks_for_it(tmp_path):
    """The policy is a caller's decision, so it is available — but it is never the default."""
    result = run(tmp_path, [pr(2, "agent", True, "andyholst")], "check", "--strict")

    assert result.returncode == 1, result.stdout
    assert "--strict" in result.stderr


def test_the_classifier_trusts_githubs_own_answer_when_it_is_present():
    """`isCrossRepository` is GitHub's statement of the fact; deriving it from the owner is a second opinion."""
    same, cross = pr_heads.classify([
        {"number": 1, "isCrossRepository": False, "headRepositoryOwner": {"login": "andyholst"}},
        {"number": 2, "isCrossRepository": True, "headRepositoryOwner": {"login": "asimov-agent"}},
    ])

    assert [p["number"] for p in same] == [1], same
    assert [p["number"] for p in cross] == [2], cross


def test_the_classifier_falls_back_to_the_owner_when_the_flag_is_absent():
    """An older payload without the flag still classifies, by the repository the head lives in."""
    same, cross = pr_heads.classify([
        {"number": 1, "headRepositoryOwner": {"login": "asimov-agent"}},
        {"number": 2, "headRepositoryOwner": {"login": "andyholst"}},
    ])

    assert [p["number"] for p in same] == [1], same
    assert [p["number"] for p in cross] == [2], cross
