"""Regression tests for the bot-outcome changed-path backstop (#3124).

These are behaviour tests: they run the helper as a CLI and assert its exit code
and stderr, not its prose. The workflow tests use a SUBSET assertion so a new
bot inherits the guard without editing this file.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "check_bot_outcome.py"
WORKFLOWS = ROOT / ".github" / "workflows"


def run_helper(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    import os
    full = dict(os.environ)
    full.update(env or {})
    return subprocess.run(
        [sys.executable, str(HELPER), "verify-changed-path", "--no-gh", *args],
        capture_output=True, text=True, cwd=ROOT, env=full, timeout=30, check=False,
    )


# AC1: no durable changed path ends non-success with no success marker.
def test_no_changed_path_fails_and_names_the_marker_refusal() -> None:
    r = run_helper("--bot", "issue-bot", "--issue", "3124",
                   "--pre-head", "abc1234", "--post-head", "abc1234")
    assert r.returncode != 0
    assert "NO CHANGED PATH" in r.stderr
    assert "bot-done" in r.stderr and "fixed" in r.stderr


# AC1: a moved head with a non-vacuous PR body is a durable changed path.
def test_moved_head_with_body_passes(tmp_path: Path) -> None:
    body = tmp_path / "pr-body.md"
    body.write_text("Issue #3124\n\nFix: real change\n", encoding="utf-8")
    r = run_helper("--bot", "issue-bot", "--issue", "3124",
                   "--pre-head", "old1234", "--post-head", "new5678",
                   "--pr-body-file", str(body))
    assert r.returncode == 0, r.stderr
    assert "durable changed path" in r.stdout


# AC1: an issue branch alone is a durable changed path.
def test_issue_branch_is_a_changed_path() -> None:
    r = run_helper("--bot", "issue-bot", "--issue", "3124",
                   "--pre-head", "same", "--post-head", "same",
                   "--branch", "agent/issue-3124-backstop",
                   "--head", "deadbeef")
    assert r.returncode == 0, r.stderr


# AC2: an empty PR body is vacuous even when the head moved.
def test_empty_pr_body_is_vacuous(tmp_path: Path) -> None:
    body = tmp_path / "empty.md"
    body.write_text("   \n", encoding="utf-8")
    r = run_helper("--bot", "fix-bot", "--issue", "3124",
                   "--pre-head", "old", "--post-head", "new",
                   "--pr-body-file", str(body))
    assert r.returncode != 0
    assert "empty PR body" in r.stderr


# AC2: a triage leg with no session is vacuous.
def test_no_session_is_vacuous() -> None:
    r = run_helper("--bot", "triage", "--issue", "3124",
                   "--pre-head", "old", "--post-head", "new",
                   "--session-created", "false")
    assert r.returncode != 0
    assert "no session was created" in r.stderr


# AC3: every outcome step that writes a marker has the guard BEFORE it.
def test_all_bot_outcome_steps_carry_the_guard_before_the_marker() -> None:
    expected = {
        "issue-bot.yml", "fix-bot.yml", "engine-bump.yml", "registry-sync.yml",
        "run-failure-reactor.yml", "rebase-bot.yml", "security-bot.yml",
    }
    actual = {
        p.name for p in WORKFLOWS.glob("*.yml")
        if "make verify-bot-outcome" in p.read_text(encoding="utf-8")
    }
    assert expected <= actual, f"missing guard: {sorted(expected - actual)}"
    for name in expected:
        lines = (WORKFLOWS / name).read_text(encoding="utf-8").splitlines()
        guard = next(i for i, l in enumerate(lines) if "Verify a durable changed path" in l)
        # The guard must come before the outcome/marker step, never after it.
        marker = next(
            i for i, l in enumerate(lines)
            if "Open the PR" in l or "Comment the outcome" in l
            or "Open / update the" in l or "- name: Report" in l
            or "Record the sweep summary" in l
            or l.strip() == "- name: make security-bot (one issue -> one green PR, or a comment instead)"
        )
        assert guard < marker, f"{name}: guard is after the marker step"


# AC4: an unrelated issue's branch is not this issue's changed path.
def test_unrelated_issue_branch_is_not_a_changed_path() -> None:
    r = run_helper("--bot", "issue-bot", "--issue", "3124",
                   "--pre-head", "same", "--post-head", "same",
                   "--branch", "agent/issue-9999-unrelated",
                   "--head", "deadbeef")
    assert r.returncode != 0


# AC5: the shared make seam calls the helper with the same contract.
def test_make_seam_calls_the_helper() -> None:
    text = (ROOT / "mk" / "bots.mk").read_text(encoding="utf-8")
    assert "verify-bot-outcome:" in text
    assert "python3 scripts/check_bot_outcome.py verify-changed-path" in text
