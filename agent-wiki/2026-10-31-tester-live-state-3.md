# the sync cycle keeps producing: a PR-head lag lesson and a committed-paths lesson

Issue #961 (row) — cycle-2 of the tester live→tree sync, immediately after #1185 merged. This clears the fresh llgenie-tester rows; it does not close #961 or #1060.

## What was measured

#1185 merged 14:52:24Z as `37764768` (run `41211337393`, 10/0 green, unit 9m03s). Within minutes the live profile grew again: `SKILL.md` +581 b and `references/agent-profile-versioning.md` +1042 b — both deltas are lessons from the #1185 fix cycle itself.

## What changed (live→tree byte-for-byte, CHECK 7/7)

1. **`gh pr view --json headRefOid` LAGS a push** — it can return the pre-push head (a max-cached read). "The PR head is the old sha" is not evidence the push failed; the authoritative tip is `git ls-remote origin <branch>`.
2. **The change→note gate reads COMMITTED paths** — `check_docs.py` diffs `git diff <base>...HEAD`, so an untracked `agent-wiki/<stem>.md` + `docs/changes.d/<stem>.md` are invisible to it. Commit the note and fragment BEFORE concluding the gate is still red. (This cost a diagnostic loop during #1185: the first `make check-docs` re-run after writing the files failed because they were untracked, not because the gate misunderstood the stem.)

## Verified

`agent_profile_sync --check` → 7/7 byte-identical; guard findings naming llgenie-tester = 0 at the head; `make check-docs` ok; lint OK — run ids in the PR bookend comment.
