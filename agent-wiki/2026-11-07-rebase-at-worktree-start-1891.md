# #1891: durable fleet rule — rebase at worktree start is a mandatory first-edit pre-flight for every lane

## What changed

Issue #1891 documents the durable fleet rule that a lane must `git fetch` the canonical upstream
`main` and `git rebase origin/main` its worktree/branch (resolving conflicts) **before the first edit
of every task** — whether starting a NEW issue/PR or UPDATING an existing one. This complements (does
not contradict) standing-rules line 28 ("Start from a fresh upstream main…", which covers branching
new work from the just-fetched sha); the new bullet makes the fetch+rebase mandatory at
resume/update too, so a paused week-old branch no longer builds stale (the #1878→#1877 and
#1887→#1886 shape) and CI stops reddening `DIRTY` with no owner.

## The canonical fleet bullet (added to standing-rules.md, verbatim in every SOUL)

"Rebase at worktree start — `git fetch` the canonical upstream `main`, then `git rebase
origin/main` the worktree/branch (resolving conflicts) before the first edit of every task, whether
starting a new issue/PR or updating an existing one; never rebase a merged branch, never through a
live run, never a shared worktree, own-branch-only, no second PR."

Load-bearing constraints embedded: never rebase/force-push a **merged** branch (#1696, read-only on
main); never rebase **through a live run** (like a body-only change, wait); never disturb a
**shared** worktree (use a fresh one); own-branch-only, force-pushed with
`--force-with-lease`/`--force-if-includes` after a fresh fetch, preserving commit authors (#840), no
second vehicle (#824).

## Files

- `agents/standing-rules.md` — one new canonical fleet bullet (the #873 single copy).
- every `agents/<profile>/SOUL.md` (13) — the bullet verbatim in each fleet block; the
  `fleet_block()` gate requires the non-exempt doc-maintainer SOUL to equal canonical verbatim.
- pointer references `references/rebase-at-worktree-start.md` in the implementer, ci-pipelines,
  pr-rebase, reviewer, and planner-orchestration skills, wired into each SKILL.md.
- note trio + `tests/test_agent_profiles.py` content-check pin.
