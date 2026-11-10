"""The measure-only worktree preflight, and the guard that keeps a bot away from the prune (issue #794).

A host bot starts work with no idea what the bench looks like, and the target that would clean it up
DELETES directories and cannot see uncommitted work — on 2026-10-28 a prune destroyed the #791 run's
worktree mid-flight. So the flow needs two things this file pins:

  * `scripts/worktree_report.py` — one row per worktree with path, branch, `merged-into-main`,
    `open-pr` and `dirty`, plus a summary, and **no mutation at all**;
  * `scripts/worktree_prune_guard.py` — a bot run (`CI`/`BOT` set) is refused unless `CONFIRM=1`,
    while the owner's own run is unchanged.

The git side is real: a real repository, real worktrees, a real squash/merge and a real dirty tree.
Only `gh` is stubbed on `PATH` — the repository's documented allowance for an external CLI — so the
logic runs against controlled API answers while every measurement happens on disk.
"""
from __future__ import annotations


from conftest import makefiles_text
import json
import os
import re
import stat
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

GIT_ENV = {
    "GIT_AUTHOR_NAME": "Andy Holst",
    "GIT_AUTHOR_EMAIL": "andy.holst@protonmail.com",
    "GIT_COMMITTER_NAME": "Andy Holst",
    "GIT_COMMITTER_EMAIL": "andy.holst@protonmail.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}


def _git(cwd: Path, *args: str) -> str:
    """One real git command in the fixture, with an identity so commits always succeed."""
    env = {**os.environ, **GIT_ENV}
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)
    assert result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr}"
    return result.stdout.strip()


def _gh_stub(tmp_path: Path, prs: list[dict], *, fails: bool = False) -> Path:
    """A `gh` on PATH that answers `pr list` from a JSON file (or fails, loudly)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    (tmp_path / "prs.json").write_text(json.dumps(prs))
    script = bin_dir / "gh"
    if fails:
        body = '#!/bin/sh\necho "HTTP 502: bad gateway" >&2\nexit 1\n'
    else:
        body = f'#!/bin/sh\ncat "{tmp_path / "prs.json"}"\n'
    script.write_text(body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return bin_dir


def _repo(tmp_path: Path) -> Path:
    """A real repository whose `origin` is a real bare repo, on `main`."""
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    origin.mkdir()
    work.mkdir()
    _git(origin, "init", "--bare", "-b", "main", ".")
    _git(work, "init", "-b", "main", ".")
    (work / "README.md").write_text("fixture\n")
    _git(work, "add", "README.md")
    _git(work, "commit", "-m", "seed")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-u", "origin", "main")
    return work


def _merged_branch(work: Path, branch: str) -> str:
    """Create `branch`, commit on it, and MERGE it into `main` — so its tip IS an ancestor."""
    _git(work, "switch", "-c", branch, "main")
    name = branch.replace("/", "-")
    (work / f"{name}.txt").write_text("landed\n")
    _git(work, "add", f"{name}.txt")
    _git(work, "commit", "-m", f"feat: {branch}")
    tip = _git(work, "rev-parse", "HEAD")
    _git(work, "switch", "main")
    _git(work, "merge", "--no-ff", "-m", f"merge {branch}", branch)
    _git(work, "push", "origin", "main")
    assert subprocess.run(["git", "merge-base", "--is-ancestor", tip, "origin/main"], cwd=work).returncode == 0
    return tip


def _unmerged_branch(work: Path, branch: str) -> str:
    """Create `branch` with a commit that is not on `main` — an in-flight attempt."""
    _git(work, "switch", "-c", branch, "main")
    name = branch.replace("/", "-")
    (work / f"{name}.txt").write_text("in flight\n")
    _git(work, "add", f"{name}.txt")
    _git(work, "commit", "-m", f"feat: {branch}")
    tip = _git(work, "rev-parse", "HEAD")
    _git(work, "switch", "main")
    return tip


def _run_report(tmp_path: Path, work: Path, prs: list[dict], *args: str,
                fails: bool = False) -> subprocess.CompletedProcess:
    """Run the report for real, with the stubbed `gh` first on PATH."""
    bin_dir = _gh_stub(tmp_path, prs, fails=fails)
    env = {**os.environ, **GIT_ENV, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    return subprocess.run(
        ["python3", str(REPO / "scripts" / "worktree_report.py"),
         "--repo", "asimov-agent/llgenie", "--base", "origin/main", *args],
        cwd=work, capture_output=True, text=True, env=env,
    )


def _row(stdout: str, path: Path) -> str:
    """The report line for *path* — one row per worktree, so a missing row is a real failure."""
    rows = [line for line in stdout.splitlines() if str(path) in line]
    assert len(rows) == 1, f"expected exactly one row for {path}, got {rows!r}\n{stdout}"
    return rows[0]


GUARD_MARKERS = ("CI", "BOT", "HERMES_KANBAN_TASK", "HERMES_KANBAN_WORKSPACE",
                 "HERMES_KANBAN_BRANCH", "HERMES_KANBAN_WORKSPACES_ROOT")


def _run_guard(*, ci: str | None, bot: str | None, confirm: str | None,
               markers: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run the guard with exactly the markers the case wants (the host's own are stripped)."""
    env = {k: v for k, v in os.environ.items()
           if k not in {*GUARD_MARKERS, "CONFIRM"}}
    if ci is not None:
        env["CI"] = ci
    if bot is not None:
        env["BOT"] = bot
    if confirm is not None:
        env["CONFIRM"] = confirm
    env.update(markers or {})
    return subprocess.run(
        ["python3", str(REPO / "scripts" / "worktree_prune_guard.py")],
        cwd=REPO, capture_output=True, text=True, env=env,
    )


def _logical_lines(text: str) -> list[str]:
    """The Makefile's recipes, with backslash continuations joined — one entry per command."""
    joined: list[str] = []
    buffer = ""
    for raw in text.splitlines():
        if raw.endswith("\\"):
            buffer += raw[:-1] + " "
            continue
        joined.append(buffer + raw)
        buffer = ""
    if buffer:
        joined.append(buffer)
    return joined



def test_report_lists_every_worktree_with_its_four_measured_facts(tmp_path):
    """Path, branch, merged-into-main, open-pr and dirty, measured for real, per worktree."""

    # Given a main checkout, a merged branch with a worktree, and an in-flight branch with a worktree
    work = _repo(tmp_path)
    _merged_branch(work, "feat/landed")
    landed = tmp_path / "wt-landed"
    _git(work, "worktree", "add", str(landed), "feat/landed")
    _unmerged_branch(work, "feat/open")
    in_flight = tmp_path / "wt-open"
    _git(work, "worktree", "add", str(in_flight), "feat/open")
    (in_flight / "uncommitted.txt").write_text("work in flight\n")

    # When  the report runs with an open PR for the in-flight branch
    result = _run_report(tmp_path, work, [{"number": 12, "headRefName": "feat/open"}])

    # Then  every worktree has a row whose four facts match the repository's real state
    assert result.returncode == 0, result.stderr
    main_row = _row(result.stdout, work)
    assert "branch=main" in main_row
    assert "merged-into-main=yes" in main_row
    assert "open-pr=no" in main_row
    assert "dirty=no" in main_row

    landed_row = _row(result.stdout, landed)
    assert "branch=feat/landed" in landed_row
    assert "merged-into-main=yes" in landed_row
    assert "open-pr=no" in landed_row
    assert "dirty=no" in landed_row

    in_flight_row = _row(result.stdout, in_flight)
    assert "branch=feat/open" in in_flight_row
    assert "merged-into-main=no" in in_flight_row
    assert "open-pr=yes" in in_flight_row
    assert "dirty=yes" in in_flight_row

    assert "summary total=3 stale=1 off-main-no-pr=0 dirty=1" in result.stdout


def test_report_mutates_nothing(tmp_path):
    """`git worktree list` and the branch set are byte-identical before and after."""

    # Given a repository with a dirty in-flight worktree and a merged one
    work = _repo(tmp_path)
    _merged_branch(work, "feat/landed")
    _git(work, "worktree", "add", str(tmp_path / "wt-landed"), "feat/landed")
    _unmerged_branch(work, "feat/open")
    in_flight = tmp_path / "wt-open"
    _git(work, "worktree", "add", str(in_flight), "feat/open")
    (in_flight / "uncommitted.txt").write_text("work in flight\n")
    worktrees_before = _git(work, "worktree", "list", "--porcelain")
    branches_before = _git(work, "branch", "--format=%(refname:short)")

    # When  the report runs
    result = _run_report(tmp_path, work, [])

    # Then  nothing on disk changed, and the dirty tree still holds its change
    assert result.returncode == 0, result.stderr
    assert _git(work, "worktree", "list", "--porcelain") == worktrees_before
    assert _git(work, "branch", "--format=%(refname:short)") == branches_before
    assert in_flight.is_dir()
    assert (in_flight / "uncommitted.txt").read_text() == "work in flight\n"


def test_report_of_a_clean_checkout_exits_zero(tmp_path):
    """Nothing stale is still a verdict: exit 0, one worktree, zero stale."""

    # Given a repository whose only worktree is the main checkout
    work = _repo(tmp_path)

    # When  the report runs
    result = _run_report(tmp_path, work, [])

    # Then  it exits 0 and its summary says one worktree, nothing stale
    assert result.returncode == 0, result.stderr
    assert "summary total=1 stale=0 off-main-no-pr=0 dirty=0" in result.stdout


def test_a_failing_gh_lookup_exits_non_zero(tmp_path):
    """An unreadable PR lookup is not reported as `open-pr: no`."""

    # Given a `gh` that fails
    work = _repo(tmp_path)

    # When  the report runs
    result = _run_report(tmp_path, work, [], fails=True)

    # Then  it exits 2 naming the failing lookup, and prints no row claiming certainty
    assert result.returncode == 2
    assert "gh pr list" in result.stderr
    assert "open-pr=" not in result.stdout


def test_the_guard_refuses_a_bot_run_without_confirm(tmp_path):
    """BOT=1 with no CONFIRM=1 is refused, and the message names the report and the re-run."""

    # Given a bot run with no confirmation
    result = _run_guard(ci=None, bot="1", confirm=None)

    # When  the guard decides
    # Then  it refuses with a message naming `make worktree-report` and `CONFIRM=1`
    assert result.returncode == 3, result.stdout + result.stderr
    assert "make worktree-report" in result.stderr
    assert "CONFIRM=1" in result.stderr
    assert "make worktree-prune" in result.stderr


def test_the_guard_refuses_a_ci_run_without_confirm(tmp_path):
    """CI=true is a bot run too — the name of the variable is not the point."""

    # Given a CI run with no confirmation
    result = _run_guard(ci="true", bot=None, confirm=None)

    # When  the guard decides
    # Then  it refuses
    assert result.returncode == 3, result.stdout + result.stderr
    assert "make worktree-report" in result.stderr


def test_the_guard_refuses_a_host_dispatched_lane(tmp_path):
    """A lane the dispatcher spawned on the host has CI/BOT absent but the dispatcher's own markers set."""

    # Given a host-dispatched lane: no CI and no BOT, but the Kanban dispatcher's workspace marker
    result = _run_guard(ci=None, bot=None, confirm=None,
                        markers={"HERMES_KANBAN_WORKSPACE": "/repo/.worktrees/t_abc"})

    # When  the guard decides
    # Then  it refuses, and the message names the marker that said "unattended"
    assert result.returncode == 3, result.stdout + result.stderr
    assert "make worktree-report" in result.stderr
    assert "HERMES_KANBAN_WORKSPACE" in result.stderr


def test_the_guard_is_a_no_op_for_the_owner(tmp_path):
    """The owner's own `make worktree-prune` behaves exactly as it did before this change."""

    # Given an owner run: neither CI nor BOT set
    result = _run_guard(ci=None, bot=None, confirm=None)

    # When  the guard decides
    # Then  it allows the prune and says nothing
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""


def test_the_guard_allows_a_bot_with_confirm(tmp_path):
    """An owner who spelled out CONFIRM=1 is obeyed, even from a bot run."""

    # Given a bot run that carries the confirmation
    result = _run_guard(ci="true", bot="1", confirm="1")

    # When  the guard decides
    # Then  the prune proceeds
    assert result.returncode == 0, result.stderr


def test_the_makefile_wires_the_report_and_guards_the_prune(tmp_path):
    """Both targets carry help + .PHONY, and the guard runs before the prune script."""

    # Given the repository's Makefile
    text = makefiles_text()

    # When  the worktree targets are read
    report_line = next((l for l in text.splitlines() if l.startswith("worktree-report:")), "")
    report_start = text.index("\nworktree-report:")
    report_block = text[report_start:].split("\nworktree-prune:", 1)[0]
    prune_start = text.index("\nworktree-prune:")
    prune_block = text[prune_start:].split("\n\n", 1)[0]
    phony_match = re.search(r"^\.PHONY:.*?(?=\n\n)", text, re.M | re.S)
    phony_text = phony_match.group(0) if phony_match else ""

    # Then  each is documented and declared, and the guard precedes the destructive script
    assert "##" in report_line
    assert "scripts/worktree_report.py" in report_block
    assert "##" in text[prune_start:prune_start + 400]
    assert re.search(r"(?<![\w-])worktree-report(?![\w-])", phony_text)
    assert re.search(r"(?<![\w-])worktree-prune(?![\w-])", phony_text)
    assert "worktree_prune_guard.py" in prune_block
    assert "worktree_prune.py" in prune_block
    assert prune_block.index("worktree_prune_guard.py") < prune_block.index("worktree_prune.py")


def test_every_agent_leg_forwards_the_bot_marker(tmp_path):
    """The guard is only real if a bot leg can receive a marker: every agent-image run forwards BOT=1."""

    # Given the repository's Makefile, one logical line per command
    text = makefiles_text()
    lines = _logical_lines(text)

    # When  every command that boots the agent image is collected
    legs = [l for l in lines if "$(AGENT_IMAGE)" in l or '"$$img"' in l]

    # Then  the marker is declared once, and no leg is left without it
    assert re.search(r"^AGENT_BOT_MARKER := -e BOT=1$", text, re.M)
    assert len(legs) >= 10, f"only {len(legs)} agent-image runs found; the roster parse is wrong"
    missing = [l.strip()[:160] for l in legs if "$(AGENT_BOT_MARKER)" not in l]
    assert not missing, "agent-image run(s) without $(AGENT_BOT_MARKER):\n" + "\n".join(missing)


def test_the_guard_reads_every_marker_a_lane_can_carry(tmp_path):
    """The guard's marker list and the Makefile's forwarded marker cannot drift apart."""

    # Given the guard's source and the Makefile's marker
    guard = (REPO / "scripts" / "worktree_prune_guard.py").read_text()
    makefile = makefiles_text()

    # When  both are read
    forwarded = re.search(r"^AGENT_BOT_MARKER := -e (\w+)=1$", makefile, re.M)

    # Then  the forwarded name is one the guard recognises, and both bot lanes are named
    assert forwarded, "AGENT_BOT_MARKER is not declared as `-e <NAME>=1`"
    assert f'"{forwarded.group(1)}"' in guard
    for lane_marker in ("CI", "HERMES_KANBAN_TASK", "HERMES_KANBAN_WORKSPACE"):
        assert f'"{lane_marker}"' in guard, lane_marker


def test_both_bot_skills_carry_the_prohibition(tmp_path):
    """Every leg preloads bot-unattended; the implementer's own skill says it too."""

    # Given the two skills a host bot preloads
    skills = [REPO / ".hermes" / "skills" / name / "SKILL.md"
              for name in ("bot-unattended", "issue-implement")]

    # When  their text is read
    texts = {path: path.read_text() for path in skills}

    # Then  each names the report target and all three forbidden commands
    for path, body in texts.items():
        assert "make worktree-report" in body, path
        assert "make worktree-prune" in body, path
        assert "git worktree prune" in body, path
        assert "git worktree remove" in body, path
        assert "Never prune a worktree" in body, path
