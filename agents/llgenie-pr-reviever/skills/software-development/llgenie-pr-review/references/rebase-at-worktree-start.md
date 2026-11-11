# Rebase at worktree start — the first-edit pre-flight (fleet rule, #1891)

The canonical rule is the #1891 bullet in `agents/standing-rules.md` — this file is the operative
pointer for this lane. It complements line 28 (branch NEW work from the just-fetched sha): the
fetch+rebase here is MANDATORY when RESUMING or UPDATING any existing worktree/branch too.

**The pre-flight, every task, no exceptions.** Before the first edit of ANY task — starting a new
issue/PR OR updating an existing one — `git fetch` the canonical upstream `main`
(`asimov-agent/llgenie`, never a fork named `origin`), then `git rebase origin/main` the worktree's
branch (resolving conflicts) onto the just-fetched sha. When this lane re-reviews an updated PR, the
head it judges must sit on the current base — a stale-base branch reds `DIRTY` and the verdict must
say so, never read stale local work as current.

**Constraints, all load-bearing:**
- Never rebase or force-push a **MERGED** branch — its ref on `main` is read-only (#1696).
- Never rebase **through a live run** at the head — wait for it (`cancel-in-progress` makes an
  authorised push destructive).
- Never disturb a **shared** worktree — use a fresh worktree.
- The rebase is on **your own branch only**, force-pushed/pushed with
  plain `--force-with-lease` after a fresh fetch (#1960: a rebased head does NOT contain the old remote tip, so the stricter includes-guarded lease would rightly refuse it), preserving commit authors (#840),
  never opening a second vehicle (#824). A branch another lane repaired is read-only.
