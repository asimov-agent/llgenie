# Fold 4 drifted engine-improver reference files live→tree (#1740, #1732 follow-up)

`make sync-agent-profile PROFILE=llgenie-engine-improver CHECK=1` at main `e7ec0795` still
reported **4 reference files differing tree-vs-live** after the #1732 fold (merge `b8590172` at
`a2a95f3a8d`): the fold snapshot (23:56:52Z) predated live edits (live mtimes 00:51–01:04Z), so
the sync gate's drop-rule correctly refused to overwrite the live-newer content — conservation,
not a bug — but it left the tree permanently behind the live profile.

## The fold (live authoritative, tree follows)

4 files copied **verbatim** from the live profile
(`~/.hermes/profiles/llgenie-engine-improver/skills/llgenie-engine-improver/references/`) into
`agents/llgenie-engine-improver/skills/llgenie-engine-improver/references/`:

- `ci-run-watching.md` 48,093 → 48,489 b
- `image-layer-caching.md` 2,970 → 7,004 b (the live-only drift listed in #1732's own row)
- `pr-gate-and-rebase-recovery.md` 13,864 → 21,250 b (same)
- `proving-and-pitfalls.md` 63,524 → 65,336 b

All four are **live-rich additive** folds (#791: never write-sync a richer live; #1724: fix the
TREE first; #1060: a live-only edit is a finding until committed under `agents/<profile>/`).
No content rewritten; byte-identical to live after the copy.

## Verified after the fold

`make sync-agent-profile PROFILE=llgenie-engine-improver CHECK=1` at the PR head reports no diff
for all four files (tree == live), closing the #1732 follow-up cleanly in the lane that found it.
