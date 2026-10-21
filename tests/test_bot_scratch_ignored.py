#!/usr/bin/env python3
"""The bots' run inputs are ignored by construction, not by a per-file denylist (issue #427).

Every bot leg writes its run input at the repo root and the push step stages with `git add -A`:

* `issue.md` — the dispatcher (scripts/issue_implementer.py),
* `triage.md` — the triage leg's verdict (issue #248),
* `refine-in.md` / `refine.md` — the refiner,
* `comment.md` — the outcome step.

Run 39513850754 shipped `triage.md` (`TRIAGE: implement`) as the "implementation" of #407 because it was
the one name missing from `.gitignore`, and the workflow answered the gap with `git reset -q -- issue.md`
— a denylist that drifts. These cases check the contract with **real git**, both directions:

* every roster name is ignored (`git check-ignore`);
* every name in the `.gitignore` run-input block is in the roster, and every roster name is written by a
  producer (Makefile / workflow / `scripts/*.py`);
* the push step carries no per-file `git reset` exclude;
* in a throwaway repository holding this `.gitignore`, a written `triage.md` is not a pending change
  while a real file is.

NO-SKIP POLICY: every case runs the real `git` binary; none is skipped.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GITIGNORE = REPO / ".gitignore"
WORKFLOW = REPO / ".github" / "workflows" / "issue-bot.yml"
MAKEFILE = REPO / "Makefile"

#: The run inputs a bot leg writes at the repo root, and where it writes them.
RUN_INPUTS = {
    "issue.md": "the dispatcher's issue + thread, read by the agent",
    "triage.md": "the triage leg's verdict (implement | refine | close)",
    "refine-in.md": "the refiner's input (issue + thread + instruction)",
    "refine.md": "the refiner's verdict",
    "comment.md": "the outcome comment posted on the issue",
}


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def test_every_run_input_is_ignored_by_real_git():
    """`git check-ignore` answers for each run input — the mechanism, not a string match."""

    # Given the repository as committed and the roster of run inputs
    assert GITIGNORE.exists()

    # When  git is asked whether each of them is ignored
    not_ignored = [name for name in RUN_INPUTS if _git("-C", str(REPO), "check-ignore", "-q", name).returncode != 0]

    # Then  every one of them is ignored, so `git add -A` cannot stage it
    assert not_ignored == [], f"these bot run inputs are NOT ignored: {not_ignored}"


def test_the_roster_matches_what_the_producers_write():
    """Neither direction can drift: what git ignores is what a leg writes, and vice versa."""

    # Given the run-input block of .gitignore and the files that write those names
    text = GITIGNORE.read_text()
    block = re.search(r"(?ms)^# --- Artifacts the bots write at the repo root.*?^comment\.md$", text)
    assert block, "the run-input block is gone from .gitignore"
    ignored = re.findall(r"(?m)^([\w.-]+\.md)$", block.group(0))
    producers = [MAKEFILE] + sorted((REPO / ".github" / "workflows").glob("*.yml")) \
        + sorted((REPO / "scripts").glob("*.py"))
    producer_text = "\n".join(p.read_text(errors="replace") for p in producers)

    # When  the two sets are compared (a name a producer writes may join the ignore block before it
    # is added to the roster — a later leg's input must not have to land in the same commit)
    only_ignored = [n for n in ignored if n not in RUN_INPUTS and n not in producer_text]
    unwritten = [n for n in RUN_INPUTS if n not in producer_text]
    not_ignored_roster = [n for n in RUN_INPUTS if n not in ignored]

    # Then  nothing is ignored by accident, no roster entry is stale, and the roster is fully ignored
    assert only_ignored == [], f"ignored but written by no producer and not in the roster: {only_ignored}"
    assert unwritten == [], f"in the roster but written by no producer: {unwritten}"
    assert not_ignored_roster == [], f"in the roster but missing from the ignore block: {not_ignored_roster}"


def test_the_push_step_carries_no_per_file_exclude():
    """The denylist that let the verdict ship is gone; the ignore file decides."""

    # Given the issue-bot workflow's commit step
    workflow = WORKFLOW.read_text()

    # When  it is read for a per-file exclude
    excludes = re.findall(r"(?m)^\s*git reset [^\n]*--\s*\S+", workflow)

    # Then  there is none, and the step still stages everything (the ignore file filters it)
    assert excludes == [], f"a per-file git reset exclude is back: {excludes}"
    assert "git add -A" in workflow


def test_a_written_scratch_file_is_not_a_pending_change(tmp_path):
    """In a real repository with this `.gitignore`, a verdict is not a pending change."""

    # Given a throwaway repository carrying this repo's .gitignore
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text(GITIGNORE.read_text())
    assert _git("-C", str(repo), "init", "-q").returncode == 0

    # When  a leg writes every run input, plus one real file
    for name in RUN_INPUTS:
        (repo / name).write_text("scratch\n")
    (repo / "real_change.py").write_text("print('hi')\n")
    status = _git("-C", str(repo), "status", "--porcelain", "--untracked-files=all").stdout

    # Then  only the real file is a change — the verdict cannot become a commit
    assert "real_change.py" in status, status
    assert not [n for n in RUN_INPUTS if n in status], status
