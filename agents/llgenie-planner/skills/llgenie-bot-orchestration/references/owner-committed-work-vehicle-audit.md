# Auditing owner-committed work: is it merged, is it vehicled, is it fresh

An owner's message "I did X, here are the logs" is a claim about *done*, exactly like a lane's
report — measure where the commit actually lives before you repeat it or build on it. The owner's
authority is not evidence that the change is on `main` or that anything will ever test it.

## Three measurements, every time

1. **Is it on `origin/main`?** A commit on any branch — however authoritative its author — is not
   merged. Read the changed line from main directly:
   `git show origin/main:<path> | grep -n '<the changed token>'`. If main still shows the old
   value (e.g. a flat cap where the branch has a matrix-aware expression), the fix is UNMERGED and
   any hold whose lift condition names it stays closed.
2. **Is the branch head of any open PR?** `gh pr list --state open --json headRefName` (or
   `--head <branch>`). Empty = the branch is **un-vehicled**: nothing on the wire, no CI will run,
   the change is invisible to reviewers and auto-merge. Un-vehicled is the common state of an
   owner's hand-pushed commit — they push a branch and never open the PR.
3. **Is the branch fresh?** `git rev-list --count <branch>..origin/main`. An owner branch dozens of
   commits behind carries stale context, will conflict on rebase, and proves nothing about current
   main until folded.

## Routing: fold onto the existing vehicle, never open a second one

Un-vehicled owner work that belongs to an issue with an in-flight branch is **folded** onto that
branch (cherry-pick / rebase its commit there as part of the open PR), not given its own PR — one
vehicle per issue. Opening a fresh PR for the same issue because the owner's branch has none is how
an issue accumulates redundant vehicles. Record the fold on the issue (owner's own motion, the
measurement, where it must land) and DM the owning implementer with the branch, the commit sha, and
what "done" means. The planner routes; the implementer pushes; nothing merges without the owner.

## A mitigation is not the remedy

If the owner's "logs" reveal the real mechanism, name both and do not let the mitigation read as
closure. Example shape: a raised timeout buys wall-clock headroom, but if the log shows the cell is
single-core-bound (a fat multi-arch compiler invoking one front-end at a time, most cores idle), the
throughput/deepening fix is still owed. The hold-lift condition that names "the fix + a genuine
successful run" is satisfied only by the fold landing AND a real completed run at the new head —
not by the branch existing.

## Never
- Never repeat "the owner did it" as "it's merged" — quote the main-path read and the PR head set.
- Never treat an un-vehicled branch as in-flight work that will surface on its own; it will not run CI.
- Never open a second PR for an un-vehicled owner commit on an issue that already has a vehicle.
