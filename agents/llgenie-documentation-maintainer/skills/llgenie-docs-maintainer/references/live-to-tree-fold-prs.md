# Live→tree fold PRs (agent profile drift)

A *fold* makes the committed tree match the LIVE profile (`~/.hermes/profiles/<p>/**`) when the
live copy is newer. Direction matters: in a fold the LIVE profile is the source of truth and the
tree follows it. This is the opposite of `make sync-agent-profile` (tree→live), and the two must
not be mixed inside one PR.

## When to run a fold

- `make sync-agent-profile PROFILE=<p> CHECK=1` reports drift and the live copy is richer
  (larger files, refs the tree lacks).
- Another lane's PR needs CHECK=1 green and hands the drift back to this lane because the files
  belong to this profile's skill — take it, file a dedicated fold issue, and keep the other
  lane's PR scoped to its own file.

Never write-mode sync a lane whose live is richer: `sync-agent-profile` without `CHECK=1` copies
tree→live and silently truncates the live file.

## Procedure

1. **File the fold issue first**, then claim it and branch from a freshly fetched
   `origin/main` (explicit refspec or API — never a sha quoted in a message).
2. **Copy the drifting files live→tree byte-identically** in a clean worktree. Copy only the
   files that actually differ; leave a file owned by another lane's vehicle out of the PR.
3. **Prove byte-identity with the tool, not by eye**: `cmp -s <tree> <live>` per file, and
   re-run it at the FINAL head right before committing — live can move while you work.
4. **Re-run CHECK=1 and expect exactly the files you did not fold.** A residual diff on a file
   another lane owns is the correct outcome, not a failure — say so in the PR body and name the
   vehicle that will clear it.
5. **Add the change→note pair**: an `agent-wiki/` note plus a `docs/changes.d/` fragment, then
   re-render `CHANGES.md`. Fragments must end with a newline or lint fails.
6. **Rebase onto a freshly fetched `origin/main` before pushing**, and redo steps 3–5 after every
   rebase: new fragments land on main, so a `CHANGES.md` rendered from the older base is stale.
7. **Push with `--force-with-lease --force-if-includes`** on your own branch only.

## Required body lines for an `agents/` PR

Both line gates are wired and required — one PR body needs all three lines:

| Line | Gate | Source |
| --- | --- | --- |
| `AGENTS: <sha>` | `make check-pr-agents-line` | `make bot-preflight` (refuses if your base is behind `origin/main`) |
| `BASE: <sha>` | `make check-pr-agents-line` | same |
| `SYNC: <profile> make sync-agent-profile PROFILE=<profile>` | `make check-pr-sync-line` | hand-written |

- The cited `AGENTS:` sha must be an ancestor of BOTH head and base, so regenerate the pair after
every rebase — `bot-preflight` exits non-zero when the base has moved.
- **A precedent PR is not proof a gate is optional.** Check whether the gate was added *after*
the precedent merged: `check-pr-sync-line` postdates the older fold that merged without a SYNC
line, so a merged green fold is not evidence the gate can be skipped today.
- **Framing the SYNC line for a fold.** The line's purpose is to report the live re-sync. In a
  live→tree fold the transfer already happened in the opposite direction and the live copy is
  the source, so the honest line reports the transfer rather than claiming a tree→live sync ran.
  Do NOT run write-mode `sync-agent-profile` in a fold PR — it would truncate the live file.
- **Body-only edits do not re-trigger CI.** GitHub keys check-runs to the head SHA. After
  changing the body to add or fix a line, re-dispatch the failed runs and read the new verdict
  at the same head; the guard reads the LIVE body, so a rerun picks up the edit.

## Rebase loop: `check-pr-base` reds on every main advance

`check-pr-base` refuses when `origin/main` moved after you cut the branch. The fix is not to
argue the check down — fetch, rebase, and redo the whole verification set at the new head:

1. `git fetch origin +refs/heads/main:refs/remotes/origin/main` (explicit refspec; the local
   `origin/main` branch shadow can hide the real tip).
2. Rebase your branch, then re-render `CHANGES.md` (new fragments), re-`cmp` every folded file,
   regenerate the AGENTS/BASE pair, and re-run lint + check-docs + the three line gates locally.
3. Force-push with lease, update the PR body to the TRUE head sha (an intermediate amended sha
   in the prose is a false claim), and confirm the pushed head on the wire before reporting.

## Closeout

- Verify the merge is an ancestor of the new `origin/main`
  (`git merge-base --is-ancestor <merge_sha> origin/main`) and that the change is present in the
  tree (`git cat-file -e origin/main:<path>`), plus zero conflict markers in `CHANGES.md`.
- Re-run the post-merge suite at a detached worktree of `origin/main`: `make lint`,
  `make check-docs`, census-gate.
- Prune what you own: remove your worktrees, delete the local branch, and let auto-merge delete
  the remote branch; prune the leftover remote ref if it lingers.
- A `root`-owned leftover inside a removed worktree's directory (e.g. a `__pycache__` written by
  a privileged run) cannot be deleted without password-gated sudo and carries no lane state —
  note it honestly and let the system temp cleaner handle it rather than fighting permissions.
