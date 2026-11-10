# Delivering the fix PR without corrupting the branch

- **Push from an explicit absolute worktree, never from ambient cwd.** `git push upstream HEAD:<branch>`
  pushes whatever HEAD the *current directory* is on. With several worktrees open for several PRs, a
  persisted or stale shell `workdir` that silently no-ops puts the WRONG tree's HEAD on your branch — a
  one-file change becomes an unrelated diff, or a stale `main` head lands on your feature branch. Pin the
  directory on every commit and push:

      git -C /abs/worktree rev-parse --abbrev-ref HEAD      # must be your branch
      git -C /abs/worktree push upstream HEAD:refs/heads/<branch>
      git -C /abs/worktree ls-remote upstream refs/heads/<branch>   # compare to local HEAD

  If the remote head differs from the local HEAD you intended, the push came from the wrong tree.
  Force-push the real head over the erroneous ref immediately — a fresh branch of your own, nothing else
  depends on it — then re-verify the PR's head from the API.

- **Never rely on a persisted terminal cwd.** If an earlier turn `cd`-ed somewhere that no longer exists,
  every later command dies before it runs and returns empty or "blocked" output that is easy to misread
  as a broken tool. Pass an absolute `workdir` on each call that changes directory, and confirm with
  `pwd` in the same command when in doubt.

- **Run a long multi-step branch/PR operation as ONE script that logs every step.** A fresh-worktree
  → write files → gate → commit → push → open-PR sequence is a dozen dependent steps; driving it as
  separate ad-hoc calls means one flaky or empty-returning call strands the run halfway and a retry
  replays completed steps against state that has already moved. Put the whole sequence in a `.sh`, `set
  -e`, append each step and its `rc` to a log file (`/tmp/<op>_progress.txt`), then read the log once
  the call returns. The log is the evidence: it shows which step succeeded, the committed head sha and
  the remote ref it pushed, so a partially-failed run is diagnosed from facts instead of guesses.

- **Read back after a fuzzy patch.** The patch tool's fuzzy matching can match loosely and corrupt a prose
  paragraph (duplicated or mangled sentence) while still reporting success. After any patch that matched
  via whitespace/strategy fallback, or that touched prose rather than code, re-read the edited region
  before committing.

- **The owner/auto-merge may merge the CURRENT head the moment checks go green — even a head you are still
  iterating.** `asimov-agent` auto-merge does not wait for your next amend; it lands whatever sha the checks
  passed on. So a green-but-incomplete intermediate head (e.g. one that compiles locally but is rejected at
  load by GitHub, or a wiring gap you were about to fix) can merge and break `main` for every lane. Two
  consequences: (a) **never push a head you would not accept as the merged result** — aliasing a secret at
  the call boundary, the change-note rider, and the `SECRET_VARS` allowlist entry must all be in the SAME
  commit you push, not a follow-up amend you assume will supersede the merge; (b) after a merge, verify
  `headRefOid` against the head you actually vouched for (`gh pr view <n> --json state,mergedAt,headRefOid`).
  If the wrong head landed, do NOT force-push the merged branch — repair `main` with a hotfix PR against the
  live tip.
- **The owner may merge mid-CI.** A partially-green PR can be merged by `asimov-agent` while you are still
  fixing a wiring gap you just discovered. Check merge state from the API before pushing amendments;
  never amend or force-push an already-merged branch. Land the outstanding fix as a follow-up PR against
  the new main tip.

- **Verify a relayed PR number before acting.** A planner or inbox message can cite a stale or wrong PR
  number or merge sha. Confirm on the live API (`gh pr view <n> --json state,headRefOid,mergedAt`) before
  arming, amending, or reporting it as fact.
