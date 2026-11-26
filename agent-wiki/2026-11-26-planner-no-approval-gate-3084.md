# 2026-11-26 — planner drops the non-existent human approval gate (issue #3084, PR #<TBD>)

The planner's versioned instruction `agents/llgenie-planner/SOUL.md` stopped saying "Every merge
needs the owner's approval; stop at the reviewable PR" and now matches the repo's actual merge
contract in `AGENTS.md` rule 7: CI lands a green, conflict-free PR with no human click, approval is
neither a precondition nor a licence to merge, `REVIEW_REQUIRED` is not a gate to wait on, and a run
in flight means take the next un-PR'd board issue end-to-end rather than idle or poll.

## What was verified

- **Why it was needed** (measured 2026-11-26, main `3cea715e3bf8`): the live instruction at
  `SOUL.md:103` contradicted `AGENTS.md:245-247` and `AGENTS.md:600`, so the planner reported two
  `REVIEW_REQUIRED` PRs (#3079, #3030) as blocked on owner approval / "no arm possible" and stopped.
  Owner corrected on 2026-11-26: no human approval is needed; this is part of the AGENTS.md behavior.
- **Change**: one line replaced in `agents/llgenie-planner/SOUL.md` with text naming CI's auto-merge
  (`mergeStateStatus == CLEAN`), the no-approval precondition, and the idle-pickup rule. No other
  file touched.
- **Gates**: `make check-file-hygiene` OK; `python3 scripts/check_pr_authors.py check` OK at the
  commit; `make check-docs` OK once this note and its `docs/changes.d/` row were added.

## Decision

- The change is a correction to my own governing instruction, so it is versioned through an issue
  (#3084) and a ready-for-review PR under `agents/llgenie-planner/`, never a silent profile edit.
  The live profile syncs from the merged text afterward.
- The `REVIEW_REQUIRED` state is left to CI's own merge logic; the planner drives PRs green + CLEAN
  and does not hand-merge or push to `main`.
