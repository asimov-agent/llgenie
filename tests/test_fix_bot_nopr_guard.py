"""The fix-bot's \"nothing to fix\" no-PR dispatch is a clean success (issue #2430).

The `Resolve the PR branch` step exits 0 with no `branch` output when it finds no open PR branch
(or a branch named main/master). Three steps still ran from that empty workspace (no checkout), and
because the #798 composite refactor made the agent leg a LOCAL action, each failed loudly:

    ##[error]Can't find 'action.yml', 'action.yaml' or 'Dockerfile' under
    .../.github/actions/agent-leg. Did you forget to run actions/checkout ...

Measured on run **42622027619** (head `8608f50e`, `workflow_dispatch`, conclusion `failure`; job
129176346780): the preflight (step 7) and the `if: always()` upload (step 10) both errored. The
workflow already guards the checkout, the loop and the push with `steps.pr.outputs.branch != ''` —
the same guard is what the leg steps that need the checkout must carry, so a no-PR dispatch skips the
whole leg and completes clean while the guarded PR path runs every step exactly as before.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WF = REPO / ".github" / "workflows"

#: The one guard the checkout, loop and push already carry (issue #2430 keeps it consistent).
GUARD = "steps.pr.outputs.branch != ''"
AGENT_LEG = "./.github/actions/agent-leg"


def _fix_steps() -> list[dict]:
    """The `fix` job's steps of `.github/workflows/fix-bot.yml`, parsed as YAML."""
    wf = yaml.safe_load((WF / "fix-bot.yml").read_text())
    return wf["jobs"]["fix"]["steps"]


def _steps_that_need_the_checkout(steps: list[dict]) -> list[dict]:
    """The leg steps that must not run from an empty (un-checked-out) workspace: the local composite
    action calls (`preflight`, `upload`) and the `make bot-sync-branch` write that needs a tree."""
    return [s for s in steps
            if s.get("uses") == AGENT_LEG or "make bot-sync-branch" in (s.get("run") or "")]


def _guarded(step: dict, *, always: bool = False) -> bool:
    """Whether `step` carries the branch guard (\u2014 the `always()` upload guard is `always() AND`)."""
    expr = step.get("if") or ""
    if always:
        return f"always() && {GUARD}" in expr
    return GUARD in expr


def test_no_pr_leg_steps_run_from_an_empty_workspace():
    """Every agent-leg step that needs the checkout carries `steps.pr.outputs.branch != ''`, so a
    no-PR dispatch skips the whole leg instead of loading `./.github/actions/agent-leg` with no tree."""

    # Given the fix-bot's `fix` job steps
    steps = _fix_steps()
    leg_steps = _steps_that_need_the_checkout(steps)
    assert leg_steps, "no agent-leg/sync step found in fix-bot.yml — the guard has nothing to pin"

    # When each step that needs the checkout is read for its `if:` guard
    for step in leg_steps:
        is_upload = step.get("name", "").startswith("Upload")
        # Then every such step is gated on a resolved PR branch (issue #2430): the no-PR path is
        # skipped clean, and on the PR path it still runs (the `always()` upload as `always() AND`).
        assert _guarded(step, always=is_upload), (
            f"{step.get('name', '(unnamed step)')} in fix-bot.yml must carry "
            f"{('always() && ' if is_upload else '')}{GUARD} so a no-PR dispatch is a clean skip")


def test_the_resolved_branch_steps_keep_their_guards():
    """The checkout, loop and push already carry the guard; they must keep it, not weaken it."""

    # Given the fix-bot's `fix` job steps
    steps = _fix_steps()

    # When the steps that gate on a resolved branch are read
    names = {s.get("name"): s for s in steps}
    for name in ("Checkout with the owner PAT (so the push re-triggers CI)",
                 "Run the fix loop INSIDE the agent image (check -> repair -> re-check)",
                 "Push the repair as ONE commit (only when the loop ended green)"):
        # Then each still carries the branch guard (never weakened, issue #2430)
        assert _guarded(names[name]), f"{name} lost its {GUARD} guard"


def test_the_guard_check_catches_a_step_without_it():
    """Negative control (issue #2430): the assertion above is real — it reds the moment a leg step
    loses its guard, so the test cannot pass on the defect it exists to prevent."""

    # Given the preflight step with its `if:` stripped
    steps = _fix_steps()
    preflight = next(s for s in _steps_that_need_the_checkout(steps)
                     if s.get("uses") == AGENT_LEG and "preflight" in s.get("name", ""))
    unguarded = dict(preflight)
    unguarded.pop("if", None)

    # When the guard check runs against it
    ok = _guarded(unguarded)

    # Then it is flagged (the pre-#2430 shape is caught)
    assert not ok, "the guard check passes on an unguarded agent-leg step — it holds nothing"

    # And stripping the `always() &&` from the upload guard is caught the same way
    upload = next(s for s in _steps_that_need_the_checkout(steps)
                  if s.get("uses") == AGENT_LEG and s.get("name", "").startswith("Upload"))
    only_always = dict(upload)
    only_always["if"] = "always()"
    assert not _guarded(only_always, always=True)
