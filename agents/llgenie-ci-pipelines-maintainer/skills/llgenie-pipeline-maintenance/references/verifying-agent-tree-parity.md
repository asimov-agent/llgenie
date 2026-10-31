# Verifying that the versioned agent tree equals the live profile

When this lane versions its own skill tree under `agents/<profile>/skills/...`, the merged snapshot is a
POINT-IN-TIME copy. It silently lags the live profile the moment the fix session itself generates a new
file (a reference authored while repairing a gate is live before it is committed). Treat parity as a
measurement, never an assumption.

## Measure parity (bytes, not vibes)

```bash
cd <worktree> && git fetch upstream main
git rev-parse --short upstream/main
for p in $(git ls-tree -r --name-only upstream/main agents/<profile>/skills/); do
  a=$(git cat-file blob upstream/main:"$p" | sha256sum | cut -d' ' -f1)
  b=$(sha256sum "$HOME/.hermes/profiles/<profile>/skills/${p#agents/<profile>/skills/}" 2>/dev/null | cut -d' ' -f1)
  [ "$a" = "$b" ] || echo "DRIFT $p"
done
```

Also list files present in LIVE but absent from the tree — a missing file is drift too and is the
common shape, because the tree only gains what a commit carried.

## Locate the live copy by the RIGHT path

A named profile's skills live under `$HOME/.hermes/profiles/<profile>/skills/<name>/SKILL.md` — NOT
`$HOME/.hermes/skills/`, which is the DEFAULT profile's home and is invisible to a named profile. Diffing
against the base path reports "file missing" and sends you to fix a non-problem; resolve the real path
with `find "$HOME/.hermes/profiles/<profile>" -path "*<skill>/SKILL.md"` first.

## A larger tree is not a newer tree — merge, never blind-copy

The tree can be LARGER than live while still MISSING live-only content (the tree keeps content a later
live edit dropped; live carries markers the tree never got). So size or a one-way `diff` never proves the
direction. Run the byte comparison AND read the differing hunks in both directions before deciding the
fix. When each side holds unique content, the versioning fix is a MERGE that keeps both — a plain `cp`
of live over the tree silently deletes the tree-only lines.

## Fix shape (one atomic commit, one vehicle)

1. `git worktree add` a fresh worktree off the merged main sha; check `git rev-parse --abbrev-ref HEAD`
   before the first edit so you are not writing into another lane's branch.
2. Copy the live file in **byte-identical** (plain `cp`, never a rewritten variant); prove it with the
   sha256 equality above — but only after the direction check above proves live is a strict superset. If
   both sides hold unique content, MERGE (keep both) instead of `cp`.
3. A new file under `agents/<profile>/skills/` is a *behavioural surface* for the change->note gate:
   add the paired `agent-wiki/<stem>.md` note and `docs/changes.d/<stem>.md` row in the SAME commit.
   See `references/change-note-gate.md`.
4. Run the gates locally against the real base before pushing:
   `python3 scripts/check_docs.py check --base upstream/main`,
   `python3 scripts/changes_index.py check`,
   `python3 scripts/check_pr_authors.py check --base upstream/main --head HEAD`,
   `python3 scripts/check_agent_skills.py check`.
   `changes_index.py check` is the fragment<->note bijection leg: it reds when a note has no
   `docs/changes.d` row OR a row points at a note that does not exist — run it alongside check_docs,
   not instead of it.
5. Push to the fork, open a ready-for-review PR (never draft), arm after all checks are green at the
   head, and read the arm back.

## Confirm after merge

Re-fetch main and re-run the sha256 comparison at the NEW head. Also read the file back from the
canonical repo (`gh api repos/<owner>/<repo>/contents/<path>` -> `size`, `sha`) so the proof does not
depend on your local clone. "Merged" and "landed correctly" are two different claims.
