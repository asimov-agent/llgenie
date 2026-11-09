# agents/llgenie-tester — #2180: fold the live profile into the tree

- **Date:** 2026-11-09 · **Issue:** #2180 · **PR:** ready-for-review PR closing #2180
- **Base:** `agents/tester-2180-fold` from `origin/main` `005d457bcbd09b491fb0915b4885ec2be6271c2a`

## The gap

`agents/llgenie-tester/` is this lane's versioned source of truth (#791), but it did not match the
lane's live host profile. Measured at `origin/main` `005d457` with the repository's own comparator
(`make sync-agent-profile PROFILE=llgenie-tester CHECK=1`):

- **4 of 9 file(s) differ.** Three are TRUNCATED in the tree (`live-longer` / `live-edited-not-tree`):
  the tree copy is a prefix of the live rulebook, so a blind tree→live sync would replace live
  behaviour. Direction is therefore **live→tree**.
- `SOUL.md` is the opposite case: the live copy is SHORTER (10,507 b) than the tree (13,634 b) —
  the tree is newer there, so it is **kept from the tree** (the sync reads it as a tree-ahead file;
  it converges to live in the post-merge #1724 flush).
- `agent-profile-versioning.md` and four other references are already at byte parity — untouched.

## What this PR folds

- The 3 truncated files copied live→tree byte-identically (raw-byte, `cmp -s` + sha256 re-hash;
  live set hash-stable across two polls before copying):

| file | live b | tree b (before) | action |
|---|---|---|---|
| `skills/llgenie-pr-testing/SKILL.md` | 100,563 | 100,420 | fold |
| `skills/llgenie-pr-testing/references/post-merge-verification.md` | 10,353 | 8,706 | fold |
| `skills/llgenie-pr-testing/references/red-job-triage.md` | 18,782 | 15,370 | fold |

- **5 SKILL-linked live-only references also folded** (the folded `SKILL.md` links them, so the tree
  SKILL would otherwise red `skill-reference-missing` and a sync would point at files it lacks):
  `gh-command-mechanics.md`, `monitoring-ci-runs.md`, `own-domain-audit.md`,
  `pr-state-inspection.md`, `verification-evidence-persistence.md` — each copied live→tree
  byte-identically.
- `SOUL.md` **kept from the tree** (live is shorter / tree appears newer); no write, no fold.
- **Not folded (out of this 9-file fold's scope, each rides its own single-file tracker vehicle):**
  live-only `issue-domain-audit.md`, `pr-body-gates.md`, `profile-parity-measurement.md`,
  `scripts/fold-live-profile.py` — none is linked by the folded SKILL.

## Verification at the committed head

- `make check-agent-profiles` (tree-only, what CI runs) → **green** (each skill's frontmatter.name
  matches its directory, body under the 100,000-char cap, no `skill-reference-missing`, SOUL rules
  present).
- `scripts/check_agent_profiles.py --only live-longer,absent-from-tree,live-lines-missing,live-edited-not-tree`
  → **0 same-lane rows** for the three truncated files after the fold (the remaining same-lane
  `absent-from-tree` rows are the four not-in-scope live-only files listed above).
- Every folded file re-hashed: raw bytes identical tree↔live at the moment of the fold.
- `make sync-agent-profile PROFILE=llgenie-tester CHECK=1` → **1 of 9 differ (SOUL.md, tree-ahead)** —
  `0 of 9` is reached after the post-merge #1724 tree→live sync that the owner lane runs.
