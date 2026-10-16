# inline-check-per-line — proposal

Issue: [#296](https://github.com/asimov-agent/llgenie/issues/296)

## Why

`scripts/code_review.py`'s `workflow-inline-scripts` check skips a whole **step block** as soon as the
block contains a make call **or** any of `gh api`/`gh pr`/`gh issue`/`gh run`/`gh search`/`gh workflow`.
A step that legitimately orchestrates with `gh` may still call a repo script on another line, and that
is exactly what `registry-sync.yml` did:

```
git config user.name "$(gh api user --jq .login)"          # gh api  -> exempted the whole block
gap="$(python3 scripts/engine_skill_gap.py report --md)"   # the violation, never reported
gh pr create --base main --head chore/registry-sync ...     # gh pr   -> exempted it again
```

Measured: the pre-fix checker reports **0** findings for that tree, the per-line checker reports **1**
naming `python3 scripts/engine_skill_gap.py`. The rule exists so a command is reusable locally and by
the pipeline and so `make check-wiring` can see it; a violation inside a `gh` step is invisible to
every gate.

## What Changes

- **`check_workflow_inline_scripts` scans per command (per line), not per block.** A `make` on the SAME
  line as a script call is the one thing that clears it; the block-level exemption (and the
  `GUARD_ALLOWED` constant it used) is gone. Orchestration-only steps still pass, because a gh/git line
  invokes no repo script.
- **`registry-sync.yml` calls a make target**: `gap="$(make engine-skill-gap-md)"`, backed by the new
  `engine-skill-gap-md` target (`scripts/engine_skill_gap.py report --md`) — the workflow keeps
  embedding the same markdown, it just reaches it the way every other step does.
- **Tests**: the hidden-call fixture (a `gh api` step with a script on another line) is a finding, a
  `make` on the same line is not, and the check runs over the REAL tree and finds nothing.
- **The consumer of that step is updated with it**: `tests/test_engine_skill_gap.py` pinned the sync
  step's own shape (`"report --md" in body`); it now pins `make engine-skill-gap-md`, so the workflow
  and the test that locks it cannot drift apart.

## Not covered

- #270 — the same class, already fixed for `queued-alarm.yml` by #277.
- #293 — the reviewer bot does not look at open PRs (a different blind spot in the same tool).
- #305 — `_steps()` yields only a workflow's LAST `run:` block (measured: `current=1` vs `real=20` for
  `ci.yml`), so this per-command scan is exercised only on the last step of each workflow. Measured
  while proving this change on the real tree; fixed by its own change, not folded in here. **Fixed by
  PR #326** (`inline-check-all-steps`): `_steps()` now returns every step (13 → 105 blocks).
- #317 — found while running `make loop` to verify this change: the loop's `test` stage runs
  `tests/test_install.py` in a `--rm` container with `HOME=/root`, where the install artifacts cannot
  exist, so the stage is red on every Linux host. Fixed by its own change, not folded in here.
  **Fixed by PR #322** (`loop-test-host-install`).
- #295 — the trigger-guard audit (queued-alarm has no guard; four accept any collaborator level).

Refs: #269 (the reviewer bot), #270, #277.
