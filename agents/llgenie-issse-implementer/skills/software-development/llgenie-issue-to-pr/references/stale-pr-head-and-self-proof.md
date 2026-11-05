# Stale PR head & independent proof

Two failure modes where GitHub's or CI's view of your head is NOT your working head.
Measure before acting; never assume.

## 1. A cross-fork force-push can leave `refs/pull/<n>/head` pinned to the OLD sha

After a rebase you force-push the fork branch. `git ls-remote <fork> <branch>` and the
fork's branches/refs API both show the NEW sha, but the parent repo's PR head — the PR
`head.sha`, `GET repos/<o>/<r>/git/ref/pull/<n>/head`, GraphQL — stays on the OLD sha,
and the timeline shows no `synchronize` event.

- **Confirm the disagreement across oracles first**: fork ref (`git ls-remote` + API) vs
  PR head (`gh pr view <n> --json headRefOid`, or the `git/ref/pull/<n>/head` endpoint).
  Fork new + PR head old + no synchronize event = GitHub's cross-fork reconciliation lag,
  NOT a real conflict and NOT a bad push.
- **Do not loop re-pushing the same sha** — it is a no-op and will not move the PR head.
- **Fix that works: push a NEW commit sha.** A content-empty commit
  (`git commit --allow-empty -m "ci: re-sync"`) moves the head sha and GitHub reconciles
  the PR to it. The empty commit is benign: the owner's squash merge drops it from main's
  history, so it costs nothing in the merged tree.
- **Do not force-push back to the pre-rebase sha to "clean up".** That is the sha
  reconciliation failed on; bouncing back re-sticks the PR head, leaving it pointing at a
  sha no longer on the fork — a strictly worse state than one benign marker commit at the tip.

## 2. When CI skipped the leg whose proof you need, prove it yourself

An earlier stage (e.g. `scope`) can short-circuit on a red so the later `linux / unit` leg
never runs — the suite was never exercised at your head and no green verdict exists for it.
Do not describe the suite as green; produce the proof.

- **Full hermetic suite**: `make test-unit` in the worktree (docker test image). It takes
  ~8–9 min — over the 420 s foreground clamp. Run it backgrounded
  (`terminal` background + `notify_on_complete`), then `process_manage` wait; read the log
  tail and the `EXIT=` marker with `cat`/`tail`, never by re-running the whole suite to
  "see the result".
- **Independent proof of what was pushed**: clone the FORK branch fresh
  (`git clone -b <branch> --single-branch <fork-url> <scratch>`), then in that clean-room
  checkout (a) `git diff <base>..HEAD --name-only` must be exactly the intended files (no
  stray `agents/` or unrelated churn), and (b) rerun the targeted tests plus the real-world
  repro. This measures the artifact a stranger receives, not your mutable working tree.
- **This clean-room clone is the sanctioned "measure the pushed artifact from an independent
  source" move** when a mutation guard keeps firing on a delivery whose real changes all went
  through `git`/`gh` subprocesses. Do the clone-and-verify proof, then hold — do NOT fabricate
  a file edit to flip a monitor that cannot observe a git-committed change.
