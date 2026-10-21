#!/usr/bin/env python3
"""The bot's implementer edits the one tree it can actually write (issue #426).

`make implement-issue` runs Hermes in a `--rm` container with exactly one writable mount,
`-v "$(CURDIR):/repo" -w /repo`. `AGENTS.md` tells an agent to work in `../llgenie-wt/<kebab>`, which
inside that container is `/llgenie-wt` — outside the mount, so it is destroyed with the container while
the agent reports success (run 39513850754 "committed" `ad266c6` there and the host never saw it).

Measured on the host with the same geometry: a write to `../llgenie-wt/probe` exists inside the
container and is absent on the host; a write to `/repo` lands. So the leg's contract has to be "edit
/repo in place", and this suite pins both halves of it: the prompt says so, and the recipe mounts one
writable tree.

NO-SKIP POLICY: both cases read the real recipe; none is skipped.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAKEFILE = (REPO / "Makefile").read_text()


def _target_body(name: str) -> str:
    """The lines of a Makefile target that actually run: its tab-indented recipe, comments skipped."""
    lines = MAKEFILE.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{name}:"))
    body = []
    for line in lines[start + 1:]:
        if line.startswith("\t"):
            body.append(line)
        elif line.startswith("#") or not line.strip():
            continue
        else:
            break
    return "\n".join(body)


def test_the_prompt_forbids_a_worktree_and_names_the_in_place_tree():
    """The agent is told which tree it can write, and that a worktree is not it."""

    # Given the internal recipe that runs Hermes for the implementer leg
    prompt = _target_body("_implement-issue")

    # When  its hard rules are read
    # Then  the container contract is explicit, and the host worktree rule is excluded by name
    assert "/repo" in prompt, "the prompt must name the tree the agent edits"
    assert "INSIDE the agent container" in prompt, prompt
    assert "do NOT create a git worktree" in prompt, prompt
    assert "in place" in prompt, prompt


def test_the_leg_mounts_one_writable_tree():
    """One mount, at /repo: a worktree path cannot resolve inside a second writable tree."""

    # Given the public implementer target that starts the container
    recipe = _target_body("implement-issue")

    # When  its mounts are counted
    mounts = [chunk for chunk in recipe.split("-v ") if ":/repo" in chunk]

    # Then  exactly one writable tree is mounted, and it is the working directory
    assert len(mounts) == 1, recipe
    assert '-v "$(CURDIR):/repo"' in recipe, recipe
    assert "-w /repo" in recipe, recipe
    assert "../llgenie-wt" not in recipe, "the leg must not hand the agent a path outside the mount"


def test_the_agent_still_does_not_commit_or_push():
    """The job owns the branch: the in-place edit is the whole of the agent's task."""

    # Given the implementer's prompt
    prompt = _target_body("_implement-issue")

    # When  its rules are read for the git actions the job owns
    # Then  the agent is still forbidden to commit, push or touch main
    assert "Do not commit" in prompt, prompt
    assert "do not push" in prompt, prompt
    assert "do not touch main" in prompt, prompt
