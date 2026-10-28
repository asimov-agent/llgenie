#!/usr/bin/env python3
"""Arming auto-merge is the producers' default, and it must stay a no-op when it has nothing to do (#912).

The failure this guards against is not "it did not arm" — it is "it armed the wrong things": a **draft** is
not a merge candidate (the repository bans drafts outright, #873), a PR that is already armed must not be
touched again, and the command must never merge by itself. All three are pinned here, driving the real CLI
through a stubbed `gh` so the argv is asserted rather than the intention.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import arm_auto_merge as arm_mod  # noqa: E402  (the real module, never a copy)


def pr(number: int, draft: bool = False, armed: bool = False, author: str = "andyholst") -> dict:
    return {"number": number, "isDraft": draft, "author": {"login": author},
            "mergeable": "MERGEABLE", "state": "OPEN",
            "autoMergeRequest": {"mergeMethod": "SQUASH"} if armed else None}


def run(tmp_path: Path, prs: list[dict], *args: str, arms: bool = True) -> subprocess.CompletedProcess:
    """Drive the real CLI. `arms=False` simulates `gh pr merge --auto` succeeding while nothing changes —
    the case a read-back exists to catch (auto-merge disabled at the repository, a PR that became a draft)."""
    log = tmp_path / "gh.log"
    listing = json.dumps(prs)
    gh = tmp_path / "gh"
    gh.write_text(f'''#!{sys.executable}
import json, pathlib, sys
log = pathlib.Path({str(log)!r})
with open(log, "a") as fh:
    fh.write(json.dumps(sys.argv[1:]) + chr(10))
if sys.argv[1:3] == ["pr", "list"]:
    print({listing!r})          # the JSON itself, not a JSON-encoded string
elif sys.argv[1:3] == ["pr", "view"]:
    calls = [json.loads(l) for l in log.read_text().splitlines()]
    merged = any(c[:2] == ["pr", "merge"] for c in calls) and {arms!r}
    print(json.dumps({{"autoMergeRequest": {{"mergeMethod": "SQUASH"}} if merged else None}}))
''', encoding="utf-8")
    gh.chmod(0o755)
    return subprocess.run([sys.executable, str(REPO / "scripts" / "arm_auto_merge.py"), *args,
                           "--gh", str(gh)], capture_output=True, text=True)


def calls(tmp_path: Path) -> list[list[str]]:
    path = tmp_path / "gh.log"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_an_open_unarmed_pr_is_armed_with_auto_and_squash(tmp_path):
    result = run(tmp_path, [pr(1)], "arm")

    assert result.returncode == 0, result.stderr
    merges = [c for c in calls(tmp_path) if c[:2] == ["pr", "merge"]]
    assert len(merges) == 1, merges
    assert "--auto" in merges[0] and "--squash" in merges[0], merges[0]


def test_a_draft_is_never_armed(tmp_path):
    """A draft is not a merge candidate; arming it queues an intent nobody can review (#873)."""
    result = run(tmp_path, [pr(1, draft=True)], "arm")

    assert result.returncode == 0, result.stderr
    assert not [c for c in calls(tmp_path) if c[:2] == ["pr", "merge"]], calls(tmp_path)
    assert "0 unarmed" in result.stdout, result.stdout


def test_an_already_armed_pr_is_touched_again_only_once(tmp_path):
    """Idempotent: a second run must not churn a PR that already carries a merge intent."""
    result = run(tmp_path, [pr(1, armed=True)], "arm")

    assert result.returncode == 0, result.stderr
    assert not [c for c in calls(tmp_path) if c[:2] == ["pr", "merge"]], calls(tmp_path)


def test_dry_reports_without_calling_merge(tmp_path):
    """`--dry` is how the producers include it without a side effect in a preview path."""
    result = run(tmp_path, [pr(1)], "arm", "--dry")

    assert result.returncode == 0, result.stderr
    assert "would arm PR #1 (squash)" in result.stdout, result.stdout
    assert not [c for c in calls(tmp_path) if c[:2] == ["pr", "merge"]], calls(tmp_path)


def test_the_report_names_the_prs_it_would_arm(tmp_path):
    result = run(tmp_path, [pr(1), pr(2, armed=True), pr(3, draft=True)], "report")

    assert result.returncode == 0, result.stderr
    assert "#1" in result.stdout, result.stdout
    assert "#2" not in result.stdout and "#3" not in result.stdout, result.stdout
    assert "1 unarmed" in result.stdout, result.stdout


def test_the_filter_is_the_drafts_and_the_armed_ones():
    """The pure predicate, so a reviewer can read the rule without running anything."""
    gone = arm_mod.unarmed([pr(1), pr(2, armed=True), pr(3, draft=True)])

    assert [p["number"] for p in gone] == [1], gone


def test_an_arm_that_changes_nothing_is_a_named_failure(tmp_path):
    """`gh pr merge --auto` can exit 0 and change nothing; the read-back is what makes "armed" a fact.

    Measured failure modes: auto-merge disabled at the repository, the PR turning into a draft, a token
    that may comment but not arm. Reporting success from the exit code alone is the same class of defect as
    reading a cancelled run as a failure.
    """
    result = run(tmp_path, [pr(1)], "arm", arms=False)

    assert result.returncode == 1, result.stdout
    assert "still carries no auto-merge intent" in result.stderr, result.stderr
    assert "were NOT armed: [1]" in result.stderr, result.stderr


def test_a_successful_arm_says_it_read_the_pr_back(tmp_path):
    """The success line must state the evidence, not the intention."""
    result = run(tmp_path, [pr(1)], "arm")

    assert result.returncode == 0, result.stderr
    assert "verified by reading it back" in result.stdout, result.stdout
