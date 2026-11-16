"""Issue #2131: the bot body-write seam refuses a write that would drop a lane's live body evidence.

Measured twice on PR #2113 (heads `ae4bb883`, `84b68fd7`): a fix-bot repair push replaced the PR body with
its own pre-fix copy, deleting the lane's `## Not covered` section and its three proven-ticked items, and
each deletion re-redded `ci-scope`'s `[check-pr-acceptance] 2 violation(s)` (runs `42448318954`,
`42449007827`) on a head the lane had already fixed. These tests drive `scripts/pr_body_write.py` over a
fixture shaped like #2113's body with `gh` stubbed on PATH (the repo's allowance, same shape as
`tests/test_fix_bot_sweep.py`): the stub answers `pr view --json body` from a state file, `pr edit`
APPLIES the proposed file to that state file (so "the section survives" is a fact about state, not a
string assertion), and `pr comment` records the body text for the AC3 claim.

Run with `make test-unit`.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEAM = REPO / "scripts" / "pr_body_write.py"
FIX_BOT_YML = REPO / ".github" / "workflows" / "fix-bot.yml"
GH_REPO = "octo/wheel"

#: A lane's live body: the four parts a lane carries, plus the `## Not covered` section and three
#: proven-ticked items a repair template does not know about — the exact shape #2131 lost twice.
LANE_BODY = """\
## Issue: #2112 — planner SOUL precedence and recall rules

Fix: pinned the precedence contract in SOUL.md and the recall rules in the triage skill.

Benefit: the planner lane applies the rulebook in the stated order on every tick.

## Acceptance criteria

- [x] the precedence section names the thread-over-body rule  (proven: run=42448318954 reviewer=owner)
- [x] the recall rule is pinned by a test  (proven: run=42449007827 reviewer=owner)
- [x] the docs pair carries the finding  (proven: rc=0 docs gate at ae4bb883)

## Not covered

- pairwise dedupe of the remainder items — filed as its own linked issue.

AGENTS: 1111111111111111111111111111111111111111 1000b 40l
BASE: 1111111111111111111111111111111111111111 (== origin/main at open)
"""

#: The pre-fix template copy #2131 measured: the same body MINUS the `## Not covered` section and the
#: three proven ticks — exactly what re-reddeled check-pr-acceptance on a head the lane had fixed.
TEMPLATE_BODY = """\
## Issue: #2112 — planner SOUL precedence and recall rules

Fix: pinned the precedence contract in SOUL.md and the recall rules in the triage skill.

Benefit: the planner lane applies the rulebook in the stated order on every tick.

## Acceptance criteria

AGENTS: 2222222222222222222222222222222222222222 1000b 40l
BASE: 2222222222222222222222222222222222222222 (== origin/main at open)
"""


def gh_stub(tmp_path: Path) -> Path:
    """A `gh` over a body-state file + a comments log; `pr edit` applies, `pr comment` records."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    body_file = tmp_path / "live-body.md"
    body_file.write_text(LANE_BODY)
    comments = tmp_path / "comments.log"
    comments.write_text("")
    log = tmp_path / "gh-calls"
    log.write_text("")
    gh = bin_dir / "gh"
    gh.write_text(f"""#!/usr/bin/env python3
import pathlib, sys
a = sys.argv[1:]
with open("{log}", "a") as fh:
    print(" ".join(a), file=fh)
if a[:2] == ["pr", "view"]:
    sys.stdout.write(pathlib.Path("{body_file}").read_text())
elif a[:2] == ["pr", "edit"]:
    new = a[a.index("--body-file") + 1]
    pathlib.Path("{body_file}").write_text(pathlib.Path(new).read_text())
elif a[:2] == ["pr", "comment"]:
    with open("{comments}", "a") as fh:
        print(a[a.index("--body") + 1], file=fh)
        print("---8<---", file=fh)
else:
    sys.exit(f"unexpected gh call: {{a}}")
""")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    return log


def run_seam(tmp_path: Path, new_body: str) -> tuple[subprocess.CompletedProcess, str, str, str]:
    """Write NEW to the stub PR and return (proc, gh-call-log, live-body-after, comments-log)."""
    body_file = tmp_path / "live-body.md"
    comments = tmp_path / "comments.log"
    new_file = tmp_path / "proposed.md"
    new_file.write_text(new_body)
    env = dict(os.environ)
    env["PATH"] = f"{tmp_path / 'bin'}:{env['PATH']}"
    p = subprocess.run([sys.executable, str(SEAM), "--repo", GH_REPO, "--pr", "2113",
                        "--new", str(new_file)], cwd=str(tmp_path), env=env,
                       capture_output=True, text=True, timeout=60)
    return p, (tmp_path / "gh-calls").read_text(), body_file.read_text(), comments.read_text()


def test_a_body_dropping_the_live_not_covered_section_is_refused(tmp_path: Path) -> None:
    gh_stub(tmp_path)
    p, calls, live_after, _comments = run_seam(tmp_path, TEMPLATE_BODY)
    assert p.returncode == 0, p.stderr  # the skip is the correct outcome, not a failure
    assert "skip" in p.stdout and "Not covered" in p.stdout  # AC1: the log names the skip + section
    assert "pr edit" not in calls  # AC1: the write never happened
    assert "## Not covered" in live_after  # AC2: the section survived the attempted write
    for tick in ("- [x] the precedence section", "- [x] the recall rule",
                 "- [x] the docs pair"):
        assert tick in live_after  # AC2: and so did its proven-ticked items
    assert "pr comment" in calls  # AC3: the decision was reported on the PR


def test_the_skip_is_reported_as_a_pr_comment_naming_the_section(tmp_path: Path) -> None:
    gh_stub(tmp_path)
    _p, _calls, _live, comments = run_seam(tmp_path, TEMPLATE_BODY)
    assert "pr comment 2113" in _calls
    assert "## Not covered" in comments  # AC3: the comment names the refused section
    assert "(proven:" in comments  # ...and the dropped proven ticks it would have deleted
    assert "issue #2131" in comments


def test_a_preserving_rewrite_reaches_the_write(tmp_path: Path) -> None:
    gh_stub(tmp_path)
    re_stamped = LANE_BODY.replace("1111111111111111111111111111111111111111",
                                   "3333333333333333333333333333333333333333")
    p, calls, live_after, comments = run_seam(tmp_path, re_stamped)
    assert p.returncode == 0, p.stderr
    assert "pr edit 2113" in calls  # a body that keeps every section may be written
    assert "## Not covered" in live_after and "(proven:" in live_after  # and it lands intact
    assert "skip" not in p.stdout
    assert comments == ""  # no skip comment for a clean write


def test_an_identical_body_writes_nothing(tmp_path: Path) -> None:
    gh_stub(tmp_path)
    p, calls, _live, comments = run_seam(tmp_path, LANE_BODY)
    assert p.returncode == 0, p.stderr
    assert "identical" in p.stdout  # the seam's own no-op, replacing fix-bot's cmp dance (#2050)
    assert "pr edit" not in calls
    assert "pr comment" not in calls
    assert comments == ""


def test_fix_bot_repairs_through_the_seam(tmp_path: Path) -> None:
    """The repair path's only body write is the seam; no direct `gh pr edit --body-file` is left."""
    yml = FIX_BOT_YML.read_text()
    assert "make bot-body-write" in yml
    assert "make bot-stamp-body" in yml
    assert "pr edit" not in yml  # fix-bot.yml carries no hand-rolled body write anywhere
    # the seam is wired to a target CI can run (AGENTS.md: workflows call make, never scripts)
    assert "\nbot-body-write: ##" in (REPO / "mk" / "bots.mk").read_text()
    assert ".PHONY: bot-body-write" in (REPO / "Makefile").read_text()
