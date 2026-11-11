# Turning a lane's gate claim into run-evidence — run it yourself at the exact head

**Trigger:** a lane (implementer, reviewer, or a monitor) reports an acceptance gate green at a
head — "check-docs rc=0", "lint passes", "criterion N-3 satisfied" — and you need that fact for a
write-back, a merge decision, or a board record. A lane's rc is a CLAIM; your own execution at the
head is the EVIDENCE.

## Recipe: detached worktree at the exact PR tip, run the target, quote the run

A detached worktree off the tip needs no branch and nothing is pushed, so it is a pure read — safe
for the planner lane (no dispatch, no branch, no peer edit).

```bash
WT=$HOME/.hermes/profiles/<profile>/cache/scratch/<tag>-check
HEADT=$(gh api repos/<o>/<r>/pulls/<N> --jq '.head.sha')      # FULL 40-char sha, never a display abbrev
rm -rf "$WT"; git -C <primary-clone> worktree add --detach "$WT" "$HEADT"
cd "$WT"
for t in check-docs check-workflows check-wiring; do
  make "$t" > /tmp/ck-$t.log 2>&1; echo "$t rc=$?"   # cite each rc AND the target's own OK line
done
```

Report each `rc=` plus the gate's own success line (e.g. `[check-wiring] OK 366 documents …`), with
the head sha. That is run-evidence a reviewer can bind a tick to, and it is independent of the lane's
assertion.

## Why this beats reading the lane's own CI

- The lane's CI run at that head may be `cancelled` or superseded by a newer push, so its green (or
  absence of a green) proves nothing about the tip you care about. Your local run at the current head
  holds regardless of what CI did.
- It converts "the implementer says it passes" into "proven at <sha> by a run I executed", which is
  exactly what a reviewer write-back and the merge gate need. Three criteria proven this way beat
  three asserted.

## Discipline

- Resolve the head with `gh api …/pulls/<N> --jq '.head.sha'` — a truncated sha makes `commits/<sha>`
  and `worktree add` fail or point at the wrong commit.
- Do not dispatch anyone to run a gate you can run yourself in one worktree. Only gates that need a
  GPU/second host, or are CI-only, are genuinely out of reach locally.
- A green local run proves the gate; it does NOT merge the PR. Arming/merging stays owner-gated.
- Leave the detached worktree in place if the session may reuse it; do not `worktree prune` or
  `worktree remove` — deletion is the owner's call.
