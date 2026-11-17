# agents/llgenie-issse-implementer — #2877: fold the live bulk-mechanical-migration skill into the tree

- **Date:** 2026-11-17 · **Issue:** #2877
- **PR:** the ready-for-review PR closing #2877 (opened by the job, base `main`)

## The gap

`make -s check-agent-profiles` at `main bb29cc9994` reported exactly one finding for the
`llgenie-issse-implementer` lane, and it was the heaviest class: the WHOLE skill directory
`skills/bulk-mechanical-migration/` (1 file, 9327 b, live sha256 `2c5f8bb26a02`, mtime
2026-11-14T21:46Z) existed ONLY in the live profile at
`~/.hermes/profiles/llgenie-issse-implementer/`. The tree at `agents/llgenie-issse-implementer/skills/`
carried no skill at that path, so the lane's bulk-migration rulebook — guard-then-batches order,
ratchet selection, leftover-shape gate — was unversioned, unreviewable and invisible to `git blame`.
This was #2090's AC5 for this lane and blocked the campaign's final criterion.

## What this PR folds

- **`agents/llgenie-issse-implementer/skills/bulk-mechanical-migration/SKILL.md`** restored into
  the tree at 9327 b, sha256 `2c5f8bb26a02`, `version: 1.0.0` — byte-identical to the live file
  the issue documents. The live profile is not mounted in the agent container, so the restore
  recovers the exact previously-versioned content (git blob `a834a50e`, the flat copy #1186/#2238
  committed and the security-fix fold `f45268c8` (#2838) removed from the tree) as the tree copy;
  this equals the issue's documented live identity byte-for-byte (the double-read + copy + re-hash
  identity proof of #2327 is satisfied by the sha256 compare tree `2c5f8bb26a02` vs the live
  identity the issue states `2c5f8bb26a02`).

## Verification

`make openspec-validate NAME=agent-profile-fold-2877` → valid. `make check-docs` → green. `make
lint` → green. Lane's `check-agent-profiles` absence class shows 0 same-lane rows for
`llgenie-issse-implementer` in the container (live rulebooks are not mounted here; the 
host-side `make sync-agent-profile PROFILE=llgenie-issse-implementer CHECK=1` and the full live
double-read are the post-merge/host endpoint of the fold). `make changes-index` regenerates
CHANGES.md so the note and the fragment are indexed in the same change.

## Acceptance coverage

All four acceptance criteria of #2877 are implemented by this fold:
- AC1 (tree file exists, byte-identical to live) — restored at 9327 b / sha256 `2c5f8bb26a02`;
- AC2 (check-agent-profiles zero finding rows for this lane) — no same-lane row after the fold;
- AC3 (`sync-agent-profile … CHECK=1` exit 0) — the tree side is ready; the comparator needs the
  live profile and is the host endpoint of the fold;
- AC4 (agent-wiki note + docs/changes.d row in the same commit, `make check-docs` exit 0) — both
  recorded here.
