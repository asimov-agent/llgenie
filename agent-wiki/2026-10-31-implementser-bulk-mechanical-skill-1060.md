# 2026-10-31 — issue #1060: version the implementer lane's bulk-mechanical-migration skill

## What

The `bulk-mechanical-migration` skill (the mechanical multi-file-migration procedure: ratchet-first,
~15-file batches, AST-not-regex select, dual-module-object trap, verify-a-batch-and-prove-failure-is-yours)
existed only on the host as `llgenie-issse-implementer/skills/software-development/bulk-mechanical-migration/SKILL.md`
(9,327 b / 163 lines). It was absent from the tree, so the lane's behaviour in that skill was unreviewable —
no diff to read when it misbehaves, and the profile-sync gate could not vouch for its content.

## The change

- `agents/llgenie-issse-implementer/skills/bulk-mechanical-migration/SKILL.md` → the live copy, byte-identical
  (9,327 b), flat layout matching the existing `containerized-repo-verification` skill in this lane's tree
  directory (`skills/<name>/SKILL.md` — not the Hermes category-nested `skills/<category>/<name>/SKILL.md`,
  which the profile checker explicitly flags as a drift source, see `scripts/check_agent_profiles.py`).

Copy direction: live → tree, byte-for-byte (`diff -q` clean). Nothing in the repo's copy existed to preserve,
so live is the authoritative source.

## The record

`make check-agent-profiles` — the gate for #1060's absent-from-tree rows — no longer reports
`bulk-mechanical-migration` as an absent-from-tree finding for the implementer lane (tree + live now agree on
the file). `ci-scope` classifies the added path as `skills` → 6 of 10 jobs run. The skill carries no
`network`-reach or secrets; `lint_linefeeds` newline-termination verified on a standalone clone at the PR head.

Issue: #1060 (does not close the tracker — this clears the implementer lane's skill row of the broader
live-only-versioning issue).

## Verification (recorded at the PR head `3a0af858`)

- `diff` live vs tree file: byte-identical.
- `check_agent_profiles.py`: OK — no absent-from-tree finding for `bulk-mechanical-migration`.
- `ci_scope.py --base origin/main`: class `skills`, 6 jobs.
- `lint_linefeeds.py` on a standalone clone: LINT OK.
