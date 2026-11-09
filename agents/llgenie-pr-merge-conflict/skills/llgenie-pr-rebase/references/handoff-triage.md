# Triage a peer lane's handoff BEFORE re-cutting its branches

A peer lane hands you a bulk finding: "these N PRs are all stale against `main`; main advanced after our cut and added gate X, so re-cut them." Treat the whole handoff as ONE collective claim to falsify before you touch a single branch. The reporter may be measuring correctly but on a premise that aged under your own prior pushes, or their tool channel may be degraded and returning stale/empty reads.

## Measure, in this order

1. **Current `main` first.** `git fetch origin +refs/heads/main:refs/remotes/origin/main` then `git rev-parse origin/main`. If main has not moved since your last sweep, the "main advanced" half of the premise is already false — say so with the sha.
2. **Each PR's live head and its parent, per PR** (never a sha quoted in the message):
   ```bash
   git ls-remote <remote> refs/heads/<branch> | awk '{print $1}'
   git rev-parse <head>^        # == current main means already current, no re-cut
   ```
   A PR whose parent already equals current `main` is current regardless of what the reporter says. Re-cutting it churns a correct branch and re-queues its matrix for nothing.
3. **Grep the head's TREE for the claimed-missing gate, not the message's count.** `git show <head>:<file> | grep -c <target>`. A gate that landed on `main` before the handoff's cut is inherited by any head already rebased onto that main — even when the reporter swears their head shows `0`. Root-cause with `git log --oneline -S <gate> origin/main` to see whether the gate predates the cut; if it does, the "main advanced and added X after our cut" claim is false.
4. **Only the genuinely-stale subset gets re-cut.** Re-cut each stale head onto current `main` as a single commit, author preserved, same branch, force-with-lease against the live wire sha, one push then freeze; gates + merge-tree before the push. Report the head sha per PR.

## The result is a partition, not a failure

Answering "2 of the 3 were already on current `main` (here are their heads); only this one was cut before the gate merged, re-cut to <sha>" is a COMPLETE, correct result. Do not invent re-cuts to match the number the reporter asked for. State the mismatch as **"expired", never "you mis-read"**: their measurement was true at the sha they quoted and simply aged under your later pushes.

## Fork push lease — pin to a LIVE sha

On a fork head, read the wire immediately before the push and use that exact sha in the explicit lease:
```bash
W=$(git ls-remote https://github.com/<fork>/llgenie.git refs/heads/<branch> | awk '{print $1}')
git push --force-with-lease=refs/heads/<branch>:$W --force-if-includes https://github.com/<fork>/llgenie.git HEAD:refs/heads/<branch>
```
The explicit form works when the leased sha is the freshly-read live wire head; the earlier rejection came from leasing a tracking-ref value that had gone stale between fetch and push, not from the form itself. If it is still rejected, fall back to plain `git push --force-with-lease <fork> <branch>`. Read back with `git ls-remote <fork> refs/heads/<branch>`.

## Foreign `bot-claim:` comments on a handed-off PR

A handed-off PR may carry a `bot-claim:` from another bot. The peer lane's explicit handoff is the authorisation; do not treat a foreign claim as a hard block, but flag in your reply that if that bot force-pushes over your head, the wire must be re-verified before relying on it.
