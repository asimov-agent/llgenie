# Bots sync with upstream `main` before they start work

Related: issue #303, issue #246 (the rebase-bot), issue #9 (never merge a PR behind main).

## The gap

| bot | what it did | what could go wrong |
|---|---|---|
| implementer | `actions/checkout@v4` then `git checkout -b "$BRANCH"` | a run that outlives a merge to `main` opened a PR already behind it |
| fix-bot | repaired the branch, then `git push origin HEAD:${BRANCH}` | it could prove a branch green against a stale base |
| rebase-bot | `git fetch origin main` → rebase (`rerere` off) → verify → `--force-with-lease` | correct — the model to copy, not the exception |

## The rule

`scripts/bot_sync_main.sh`, in two verbs, both failing loudly when `main` is unreachable:

- **`reset`** (`make bot-sync-main`) — before implementing a NEW issue: fetch upstream `main` and
  hard-reset the tree, so the branch that gets pushed starts from latest `main`.
- **`rebase`** (`make bot-sync-branch`) — before repairing an EXISTING PR: replay the branch's own
  commits on top of latest `main`, with `rerere` off (a recorded resolution from an earlier rebase
  is not trustworthy).

A conflict is **not** resolved here: the script aborts, leaves the branch exactly as it found it,
and exits **2** — the fix-bot reports it and stands down, because conflict resolution is the
rebase-bot's job.

## Push semantics

The fix-bot used to push a plain fast-forward, which is what made a collision with the rebase-bot
harmless (the second push is rejected). A sync rewrites history, so that push is now
`--force-with-lease` **to the PR's own head remote**: if another bot pushed in the meantime, this
push is rejected loudly rather than clobbering it. The property is preserved — the loser fails
visibly — it is just carried by a lease on both sides now instead of plain-vs-forced.

## How it is verified

`tests/test_bot_sync.py` runs against a **real scratch git repository** (a bare origin plus a clone
whose `main` advances after the branch forks): the branch ends up containing latest `main` with its
own work intact, `reset` makes the tree exactly `main`, a conflicting branch is left untouched with
no rebase in progress, and an unreachable remote fails with "refusing to start". A final test
asserts both workflows actually call the targets, so the rule cannot rot into a script nobody runs.
