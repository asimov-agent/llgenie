# Owner focus discipline & independent verification

## The owner's "focus only on <PR>" outranks every background monitor

When the owner names a single PR and says to drop everything else ("resolve the
conflicts and make the pipeline green for <n>" — often with visible frustration after
you narrated other vehicles), that is the whole job:

- **Suspend the other vehicles.** Stop polling and reporting their CI, do not post their
  status next to the named PR, and do not touch them. The named PR's conflicts + green
  pipeline is the ONLY deliverable until it is done.
- **Do not cancel live runs.** Leaving a run in flight is correct; just stop looking at
  it and stop talking about it. Cancelling to "clear the board" destroys matrices.
- **Do not interleave status.** A reply that reports the named PR's progress and then
  appends "meanwhile #x is still building" reads as ignoring the directive. Report only
  the named PR until it is green; mention the others only if the owner asks.
- If the one blocker on the named PR is a designed gate self-red (e.g. an unticked issue
  AC, cleared only by reviewer `--proven` write-back), say so plainly and drive the actual
  fixable reds first; do not scatter attention across other PRs while it resolves.

## A git WORKTREE breaks git-reading tests — prove in a standalone clone

A worktree's `.git` is a FILE (a gitfile pointing at the parent gitdir), not a directory.
Any test that runs `git rev-parse` / reads `.git` / checks ancestry reds with a gitfile
artifact that has nothing to do with your diff (e.g. a pin-published check, a base-line
check).

- A worktree run showing 1–2 such failures amid ~all-pass is NOT a regression; do not
  chase it as one.
- Re-run the SAME suite in a standalone full clone at the same head (clone the repo and
  `git fetch <fork-or-remote> <branch>` then check it out, or `git clone -b <branch>` the
  fork). Git-reading tests pass there, and that green is the honest proof — cite it with
  the head sha and state the worktree failures were the gitfile artifact.

## gh works from execute_code when wrapped in the login shell

Direct `subprocess.run(['gh', ...])` from the execute_code kernel fails (PATH/auth not
loaded). But `subprocess.run(['bash','-lc','gh ...'])` goes through the LOGIN shell, which
sources the mise/profile env, so gh and its token resolve and real JSON comes back. This
is the way to batch many gh reads cheaply in execute_code; always parse the returned JSON
to confirm it is real (never trust the exit code). Direct `['gh',...]` without `bash -lc`
still fails, so keep `bash -lc` in every call.
