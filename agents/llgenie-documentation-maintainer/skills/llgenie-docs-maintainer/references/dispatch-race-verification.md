# Reconciling a dispatch that raced an already-landed fix

A dispatch can arrive *after* the issue is already CLOSED and its fix merged by another vehicle — an
owner-lane PR landing in the same minute the planner queued the dispatch. The dispatch's sha and its
"needs this" framing are then both stale. Never cut a branch off a dispatch on trust.

## Verify, in this order, before a worktree / branch / first edit

1. **Issue state** — `gh issue view <n> --repo asimov-agent/llgenie --json state,closedAt,title`.
   `CLOSED` (or a `closedAt` earlier than now) means stop and reconcile, do not implement.
2. **The closing vehicle** — `gh pr list --repo asimov-agent/llgenie --search '<n> in:body'
   --json number,state,title` and `git ls-remote origin 'refs/heads/*<n>*'`. Find the PR whose body
   says `Closes #<n>`; also catch a live branch another lane already claimed (#824 duplicate-race).
3. **The real tip** — `git fetch origin +refs/heads/main:refs/remotes/origin/main` (explicit refspec;
   never trust the local `origin/main` shadow), then compare `git rev-parse origin/main` to the sha
   the dispatch quotes. Main usually advances past it — a quoted sha is stale by the time it is read.
4. **Acceptance in a throwaway worktree** at origin/main:

   ```
   git worktree add --detach /tmp/wt-<n> origin/main
   cd /tmp/wt-<n> && make -s check-docs      # must print ok: ... and exit 0
   cd - && git worktree remove /tmp/wt-<n> --force && git worktree prune
   ```

   Read the landed note/trio content — confirm it names the correct PR number and merge sha and
   covers the behavioural change the issue describes. Measure, don't eyeball.

## If acceptance already holds

- Comment the evidence on the issue: issue closed at `<ts>`, closing PR `#<m>` merged as `<sha>`,
  `make check-docs` exit 0 at `<tip>`, note names the right PR/merge-sha.
- Report to the planner: "no new vehicle owed" — a duplicate re-opens nothing and burns a gate run.
- Never re-close the issue, never rebase or re-push the merged vehicle, never arm a duplicate (#1088).

## If acceptance does NOT hold

The gap is real work: cut the branch from the freshly fetched origin/main sha, write it into the
first comment, and land the trio normally — still no merge/arm of the merged base (#1088).
