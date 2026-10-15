# Bot sync with upstream main before starting work

## Why

A bot could do correct work on a **stale base**. The implementer opened a PR from whatever
`actions/checkout` had when the run began, so a run that outlived a merge to `main` produced a PR
that was already behind it; the fix-bot repaired a branch without ever consulting `main`, so it
could prove a branch green against a base that no longer existed. Issue #9 set the principle - never
merge a PR behind `main` - and the rebase-bot (#246) implements it for a PR that is *already* open.
Nothing applied it at the moment a bot *starts*.

## What changes

- `scripts/bot_sync_main.sh` with two verbs, `reset` and `rebase`, both failing loudly when
  upstream `main` cannot be reached.
- `make bot-sync-main` (the implementer, before it picks an issue) and `make bot-sync-branch`
  (the fix-bot, before its repair loop).
- A sync that conflicts **exits 2 and changes nothing**: resolving it is the rebase-bot's job.
- The fix-bot's push becomes `--force-with-lease` to the PR's own head remote, because a sync
  rewrites history; a concurrent push is then rejected loudly rather than clobbered.
- Tests drive all of it through a real scratch git repository, and assert both workflows call it.
