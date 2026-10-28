# worktree-prune-leftover — proposal

Issue: [#759](https://github.com/asimov-agent/llgenie/issues/759)

## Why

`make worktree-prune` unregisters a merged worktree and deletes its branch, but when a
containerized `make test-unit` run has left root-owned files inside that worktree, the
directory survives the removal: a partial copy of the repository sitting beside the
checkout, invisible to `git worktree list`, that `git worktree prune` cannot clear and
`rm -rf` as the owner cannot delete either.

Worse, the first non-dry run reports a failure while having done half the work
(`make: *** [Makefile:780: worktree-prune] Error 2`), so the exit code says "the sweep
failed" when the branch delete had already succeeded and only an undeletable directory
was left behind. That is the same confusion #593 fixed for a different refusal: an
unexpected partial state read as a broken tool.

## What Changes

- `apply()` treats a worktree it could not remove as a **named leftover**: the path, the
  reason, and the one command that clears it are printed; the branch is still deleted.
- The sweep's exit contract becomes "0 when every planned action either happened or was
  reported as a keep/leftover with its reason". A leftover is not an error.
- Where the tool can, it deletes the debris through the container engine as root — the
  same engine that created the root-owned files — and then retries the removal, so the
  common case needs no human step.
- `tests/test_worktree_prune.py` drives the real `apply()` against a worktree holding a
  file the current user cannot delete (a read-only directory) and asserts the leftover
  report plus the exit code.

## Out of scope

- Removing root-owned files from the *live* worktree during a test run (#433) — this is
  the sweep's recovery, not the cause.
- Deleting the fork's branch of a merged PR (#432).
- Changing which branches the planner considers prunable (#431, #593).
