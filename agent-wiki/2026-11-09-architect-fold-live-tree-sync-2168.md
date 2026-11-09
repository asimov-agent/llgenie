# llgenie-architect: fold live→tree, then sync, so a rebuild cannot downgrade the lane (#2168)

## What changed

`agents/llgenie-architect/` is this lane's versioned source of truth (#791). At `origin/main
54ff1145` the tree and the live profile diverged on **4 of 10** compared files; two of them were
**truncated in the tree** — the live profile carried more behaviour than the committed copy, so a
routine `make sync-agent-profile` would have replaced ~14 KB of live rulebook with an older seed, and a
rebuild from the tree would have come up with *less* behaviour (no error, just a thinner agent).

This change folds the live profile's behaviour into the tree, per-file, in the direction that can
never lose rulebook:

| file | resolution | reason |
|---|---|---|
| `SOUL.md` | **fold live→tree** (13,406 b → 13,432 b) | the first fold kept tree (live was 3,127 b behind). After merge the live profile moved to the `never-merge` wording (issue #1259, `dc94336f`) while the tree still said `never-implement` — live is now the newer, richer side, so this re-fold carries live's lines 42–44 (`agents/manifest.json` lists `never-merge` only for this profile) byte-identical into the tree; `CHECK=1` re-measured **0 of 12 differ** at the fixing head |
| `references/fleet-idle-audit.md` | **keep tree** | exists only in the tree; restored into the live profile by the post-fold sync |
| `skills/.../SKILL.md` (1.4.0 → 1.4.3) | **fold live→tree** | tree was the truncated 1.4.0 seed (89,035 b vs live 100,286 b); live carries the full 1.4.3 rulebook including the `$HOME`-authoring rule (#2145) and the measure-drift-read-only duty |
| `skills/.../references/ci-run-state-triage.md` | **fold live→tree** | tree lacked live's §7 (live-state gates) and §8 (a dispatch's base sha is a claim about time) — 2,970 b of live behaviour |
| `skills/.../references/home-path-migration.md` | **fold live→tree** | live-only reference cited by the folded SKILL.md (#2145 sweep procedure); without it the folded SKILL would name a missing reference |
| `skills/.../references/live-profile-parity.md` | **fold live→tree** | live-only reference cited by the folded SKILL.md (the measure-drift-report-direction recipe) |

Every "fold live→tree" file was verified byte-identical to its live counterpart, and the tree-origin
files were line-subset-checked so **no live rulebook line is lost**: `comm -23 <(sort live/SOUL.md)
<(sort tree/SOUL.md)` is empty.

## Why it matters

The tree is decorative until it matches what the lane actually runs. A rebuild materialises the tree
into the profile (#2165); with the tree truncated, a rebuilt `llgenie-architect` would silently come
up with less behaviour — the loss produces no error because a shorter skill doesn't fail, it just
behaves differently. Folding live→tree first, then syncing tree→live, makes the committed behaviour
identical to what the lane runs, so a review of `agents/llgenie-architect/` is a review of the agent
and a rebuild is a no-op rather than a downgrade.

## Deliberate non-changes

- `SOUL.md` was **kept tree** in the first fold (live was 3,127 b behind — issue §4's "live shorter → keep tree and say so"), but on this re-fold it is carried **live→tree**: the live profile moved to the `never-merge` wording (#1259) after the first fold, so live is now the newer side and the tree was re-folded to match (13,432 b byte-identical). `references/fleet-idle-audit.md` remains **kept tree** (exists only in the tree).
- The obsolete live-only `.hermes/skills` older set and the other 12 lanes' drift are explicitly out of
  scope (see issue's Not covered: #2165, #2135).

## Verification

- `make sync-agent-profile PROFILE=llgenie-architect CHECK=1` → **0 of 12 file(s) differ**
- `make check-agent-profiles-ratchet` → OK (no committed-tree finding past the baseline)
- Folding direction: no tree→live sync ran onto a truncated tree; the folded commit lands first
- Every folded file is `cmp`-identical to its live counterpart
