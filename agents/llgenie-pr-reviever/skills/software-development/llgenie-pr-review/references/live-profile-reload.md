# Reloading a lane's live profile from the versioned tree

When the directive is *"reload your SOUL and skills from upstream main; ensure the live profile matches",*
the job is a byte-for-byte **sync of the derived copy from the source of truth**, not a review and not a
new PR. The repo tree under `agents/<lane>/` at current upstream `main` is authoritative (it is versioned
behaviour, changed only by issue+PR). The live profile at
`~/.hermes/profiles/<lane>/<rel>` is a *derived copy* and drifts in **both** directions:

- **live grew, tree behind** → `LIVE-LONGER`; this is the versioning-PR violation the `--soul-shrink`
  check and the "A versioning PR is a checkpoint, not a state" section describe. The remedy is a PR that
  captures the grown live content into the tree.
- **tree ahead of live** → `main` landed a change (a behaviour edit already merged) and the live copy was
  never synced to it. This is what a *reload* directive targets. The remedy is **sync from `main` INTO the
  live profile** — NOT a PR, because the content is already landed and versioned; you are only aligning a
  stale copy, which is not a private behaviour edit.

## Procedure

1. **Fetch the real tip and cross-check it twice.** Never trust a sha quoted in a dispatch or chat message.
   ```bash
   cd <repo>
   git fetch origin refs/heads/main:refs/remotes/live/main -q
   echo "LIVE: $(git rev-parse refs/remotes/live/main)"
   echo "API:  $(gh api repos/asimov-agent/llgenie/commits/main --jq .sha)"   # must equal LIVE
   ```
2. **Diff every file the lane owns against its live counterpart.** Do not spot-check; enumerate the tree.
   ```bash
   PROF=~/.hermes/profiles/<lane>
   git ls-tree -r --name-only live/main agents/<lane>/ | while read f; do
     rel="${f#agents/<lane>/}"; live="$PROF/$rel"
     if [ ! -f "$live" ]; then echo "MISSING in live: $rel"
     elif ! diff <(git show "live/main:$f") "$live" >/dev/null 2>&1; then echo "DIFFERS: $rel"; fi
   done
   ```
3. **Sync only the diverged files, straight from `git show`.** Never hand-retype; never edit the live copy
   directly, because a private edit is exactly what the versioned-behaviour rule forbids and it will differ
   from the tree again on the next reload.
   ```bash
   for rel in SOUL.md skills/…/SKILL.md skills/…/references/<x>.md; do
     git show "live/main:agents/<lane>/$rel" > "$PROF/$rel"
   done
   ```
4. **Re-diff to prove `MATCH` on every file you touched.** Report *"N of M verified byte-identical
   repo↔live at `<sha>`"* — a claim about a specific main sha, which expires when main moves, never
   "the profile now matches live" (no expiry, false within the hour).

## Why this is not "implementing"

Syncing a derived copy to already-landed, already-merged versioned content is not writing behaviour — the
behaviour PR already exists. Creating a new PR to push main's content into the live copy would be a
no-op PR against a change that is already on `main`. The distinction to state out loud: *"these are
already-landed changes I am aligning the live copy to, not new behaviour edits."*

## Report shape

```
BOT <lane> · RELOADED · main <sha> · SOUL + SKILL + N references byte-identical repo↔live (verified)
```

If any file is `MISSING in live` (a file the tree carries that the profile lacks entirely), that is the
same sync — copy it in and confirm it lands; `MSISING` and `DIFFERS` are the same remedy here.
