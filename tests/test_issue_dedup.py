#!/usr/bin/env python3
"""The duplicate sweep: candidate selection, the pair, and the close (issue #553).

Business logic is never mocked: the real `best_pair`/`parse_verdict`/`apply_verdict` run. Only the
external system (`gh`) is a stand-in, and it is a real script on PATH whose argv is recorded, so the
tests assert on the exact calls the bot would make.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

from scripts import issue_dedup as dedup

REPO = "asimov-agent/llgenie"


def _fake_gh(tmp_path: Path, issues: list[dict], meta: dict | None = None) -> Path:
    """A `gh` that answers `issue list`/`issue view` and records every mutating call."""
    log = tmp_path / "gh.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(f"""#!{sys.executable}
import json, sys
args = sys.argv[1:]
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps(args) + "\\n")
ISSUES = json.loads({json.dumps(issues)!r})
META = json.loads({json.dumps(meta or {})!r})
if args[:2] == ["issue", "list"]:
    print(json.dumps(ISSUES)); sys.exit(0)
if args[:2] == ["issue", "view"]:
    num = args[2]
    print(json.dumps(META.get(num, {{"state": "OPEN", "labels": [], "title": ""}}))); sys.exit(0)
sys.exit(0)
""")
    gh.chmod(0o755)
    os.environ["PATH"] = f"{bin_dir}:{os.environ['PATH']}"
    return gh


def _calls(log: Path) -> list[list[str]]:
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def _issue(num: int, title: str, body: str, when: str, labels: list[str] | None = None) -> dict:
    return {"number": num, "title": title, "body": body, "createdAt": when,
            "labels": [{"name": n} for n in (labels or [])]}


# ---- candidates: a claimed issue is never touched ----

@pytest.mark.parametrize("label", ["agent:implement", "agent:ready", "agent:refined", "agent:closed",
                                   "agent:duplicate"])
def test_a_claimed_issue_is_never_a_candidate(label):
    """Every agent label means claimed: the sweep cannot race the bots that do the work."""

    # Given an issue carrying one agent label
    issue = _issue(1, "x", "y", "2026-10-01T00:00:00Z", [label])

    # When  candidacy is decided
    # Then  it is protected
    assert dedup.is_protected(issue) is True


def test_candidates_drop_every_claimed_issue(tmp_path):
    """The list the pair is chosen from excludes them all."""

    # Given three open issues, one claimed for implementation
    issues = [_issue(10, "flaky top-tier on macos", "the macos top-tier job fails intermittently", "2026-10-01T00:00:00Z"),
              _issue(11, "flaky top-tier job", "top-tier fails intermittently on macos runners", "2026-10-02T00:00:00Z"),
              _issue(12, "engine bump", "bump tensorfold", "2026-10-03T00:00:00Z", ["agent:implement"])]
    gh = _fake_gh(tmp_path, issues)

    # When  the sweep lists candidates
    free = dedup.candidates(str(gh), REPO)

    # Then  the claimed issue is absent and the two free ones remain
    assert [i["number"] for i in free] == [10, 11]


# ---- the pair ----

def test_the_most_similar_pair_is_chosen_with_the_older_one_canonical():
    """The older issue is the canonical one: the copy is what gets retired."""

    # Given two near-identical issues and one unrelated
    issues = [_issue(20, "top-tier job fails intermittently on macos", "the macos top-tier check flakes", "2026-10-01T00:00:00Z"),
              _issue(21, "bump tensorfold to 1.0.7", "engine bump", "2026-10-02T00:00:00Z"),
              _issue(22, "macos top-tier job fails intermittently", "the top-tier check flakes on macos", "2026-10-03T00:00:00Z")]

    # When  the best pair is computed
    found = dedup.best_pair(issues)

    # Then  it is #20 (older) as canonical and #22 (newer) as the copy
    assert found is not None
    canonical, copy, score = found
    assert (canonical["number"], copy["number"]) == (20, 22)
    assert score >= dedup.THRESHOLD


def test_pick_writes_the_pair_for_the_agent_leg(tmp_path, monkeypatch):
    """The agent reads one file: both bodies, the score, and what to answer."""

    # Given two similar unclaimed issues
    issues = [_issue(30, "duplicate sweep missing", "no bot looks for duplicate issues", "2026-10-01T00:00:00Z"),
              _issue(31, "no duplicate cleaner bot", "nothing looks for duplicate issues in the backlog", "2026-10-02T00:00:00Z")]
    gh = _fake_gh(tmp_path, issues)
    monkeypatch.chdir(tmp_path)

    # When  the pick runs
    picked = dedup.pick(str(gh), REPO)

    # Then  it names both issues and writes dedup-in.md
    assert picked and picked["canonical"] == 30 and picked["copy"] == 31
    text = (tmp_path / "dedup-in.md").read_text()
    assert "#30" in text and "#31" in text and "EVIDENCE" in text


# ---- the close ----

def test_a_duplicate_close_retires_the_copy_and_queues_the_canonical(tmp_path):
    """One comment citing the canonical, the label, the close — and the canonical goes into the queue."""

    # Given a free copy whose canonical is unqueued
    gh = _fake_gh(tmp_path, [], meta={"31": {"state": "OPEN", "labels": [], "title": "copy"},
                                      "30": {"state": "OPEN", "labels": [], "title": "canonical"}})
    log = tmp_path / "gh.log"

    # When  the verdict says duplicate of #30
    dedup.apply_verdict(str(gh), REPO, 31,
                        "DUPLICATE: #30\nEVIDENCE: both report the same missing sweep\n")

    # Then  the copy is commented, labelled and closed, and #30 is queued
    calls = _calls(log)
    comment = [c for c in calls if c[:2] == ["issue", "comment"]]
    assert comment and comment[0][2] == "31" and "#30" in " ".join(comment[0])
    assert [c for c in calls if c[:2] == ["issue", "edit"] and "agent:duplicate" in c]
    assert [c for c in calls if c[:2] == ["issue", "close"] and c[2] == "31"]
    assert [c for c in calls if c[:2] == ["issue", "edit"] and c[2] == "30" and "agent:implement" in c]


def test_a_duplicate_close_without_evidence_is_refused(tmp_path):
    """The implementer's rule applies here too: no evidence, no close."""

    # Given a verdict with no EVIDENCE block
    gh = _fake_gh(tmp_path, [], meta={"31": {"state": "OPEN", "labels": []}})

    # When  the verdict is applied
    with pytest.raises(SystemExit) as exc:
        dedup.apply_verdict(str(gh), REPO, 31, "DUPLICATE: #30\n")

    # Then  it fails loudly and mutates nothing
    assert "EVIDENCE" in str(exc.value)
    assert not _calls(tmp_path / "gh.log")


def test_the_copy_is_never_touched_when_it_carries_an_agent_label(tmp_path):
    """Belt and braces: the candidate filter already excludes it, and the apply path re-checks."""

    # Given a copy that carries agent:implement by the time the verdict lands
    gh = _fake_gh(tmp_path, [], meta={"31": {"state": "OPEN", "labels": [{"name": "agent:implement"}]}})

    # When  the verdict says duplicate
    dedup.apply_verdict(str(gh), REPO, 31, "DUPLICATE: #30\nEVIDENCE: same behaviour\n")

    # Then  nothing is closed
    assert not [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["issue", "close"]]


def test_a_distinct_verdict_leaves_both_issues_open(tmp_path):
    """Most similar pairs are not duplicates; the bot must be able to say so and do nothing."""

    # Given a DISTINCT verdict with its reason
    gh = _fake_gh(tmp_path, [])

    # When  it is applied
    dedup.apply_verdict(str(gh), REPO, 31, "DISTINCT:\nREASON: one is about macOS, the other about CUDA\n")

    # Then  neither issue is edited or closed
    assert not [c for c in _calls(tmp_path / "gh.log") if c[:2] in (["issue", "close"], ["issue", "edit"])]


def test_a_bot_generated_tracker_issue_is_not_a_candidate(tmp_path):
    """Two architecture-refresh issues are near-identical by construction, not duplicates (measured #494/#517)."""

    # Given two bot-generated trackers and one human issue
    gen = "<!-- architecture-bot:20261021T1814 -->\n\nIssue: docs/ARCHITECTURE.md is stale"
    issues = [_issue(494, "docs(architecture): refresh docs/ARCHITECTURE.md for the tree at A", gen, "2026-10-21T00:00:00Z"),
              _issue(517, "docs(architecture): refresh docs/ARCHITECTURE.md for the tree at B", gen, "2026-10-22T00:00:00Z"),
              _issue(500, "the top-tier job flakes on macos", "intermittent failure", "2026-10-20T00:00:00Z")]
    gh = _fake_gh(tmp_path, issues)

    # When  candidates are listed
    free = dedup.candidates(str(gh), REPO)

    # Then  only the human issue remains — a generated pair can never be "the same defect"
    assert [i["number"] for i in free] == [500]
