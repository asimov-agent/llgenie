# agents/llgenie-business-analyst — #2169: live→tree profile fold (SKILL.md), rebuild-parity proof

- **Date:** 2026-11-09 · **Issue:** #2169 · **PR:** ready-for-review PR closing #2169
- **Branch:** `llgenie-wt-2169-fold` (from `origin/main` `8608f50e132ae3793f8ab76f33c9a37e20aefe88`; originally cut from `ffac2227`, rebased onto fresh main before landing)

## The gap

`agents/llgenie-business-analyst/` is this lane's versioned source of truth (#791), but it did not
match the live host profile. At `origin/main` `ffac2227` the repository's own comparator reported

```
make sync-agent-profile PROFILE=llgenie-business-analyst CHECK=1 -> 2 of 3 file(s) differ
```

| file | tree b | live b | verdict |
|---|---|---|---|
| `SOUL.md` | 12,283 | 9,156 | tree longer/newer — KEEP TREE (live behind) |
| `skills/llgenie-business-analyst/SKILL.md` | 7,604 | 14,136 | tree TRUNCATED — fold LIVE→TREE |
| `skills/llgenie-business-analyst/references/issue-body-shape.md` | 1,931 | 1,931 | identical — no change |

With the tree truncated, a rebuild from the tree would materialise *less* behaviour than the lane
runs today (the #2165 provisioning path), silently downgrading the lane — the loss produces no error.

## What this PR folds

- `skills/llgenie-business-analyst/SKILL.md` copied **live→tree byte-identically** (7,604 → 14,136 b),
  restoring the full live file — not patched around the truncation. One refinement: the live copy's
  host-bot-tools marker block was STALE (predates #1572, which added this lane to
  `tests/fixtures/host-bot-capabilities.json`), so it was re-stamped to the fixture render — otherwise
  `test_host_bot_capabilities.py` reds at the committed head. Final file is 13,989 b both sides; the
  tree→live sync carries the corrected marker into the live profile.
- `SOUL.md`: **tree kept** (12,283 b). The live copy (9,156 b) is behind; the tree is newer. The
  fix syncs tree→live (grows live, allowed, #791 step 4 opposite-direction case) — it is NOT copied
  live→tree.
- `references/issue-body-shape.md`: untouched (identical 1,931/1,931).

## Verification

- Byte identity per file: `cmp -s ~/.hermes/profiles/llgenie-business-analyst/{SOUL.md,skills/llgenie-business-analyst/SKILL.md,skills/llgenie-business-analyst/references/issue-body-shape.md} agents/llgenie-business-analyst/<same>` → all identical after the tree→live sync.
- `make sync-agent-profile PROFILE=llgenie-business-analyst CHECK=1` → **0 of 3 file(s) differ** at the head.
- `make check-agent-profiles` green at the head; change scoped to this profile only.
