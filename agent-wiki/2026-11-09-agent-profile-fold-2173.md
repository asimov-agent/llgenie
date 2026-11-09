# agents/llgenie-issse-implementer — #2173 (re-open): live→tree profile fold of new drift

- **Date:** 2026-11-09 · **Issue:** #2173 (re-opened) · **PR:** ready-for-review PR closing #2173
- **Branch:** `agents/2173-impl-fold-4aaac2c1` (from `origin/main` `4aaac2c1df885e7d99ecdc8e2bb25d13efb84d9f`)

## The gap

Prior fold #2238 (commit `0bba737f`, merged 2026-11-08) versioned the live profile into the tree for
the first time, but the live profile kept being written by the owning lane, so at the dispatch's
measurement `make sync-agent-profile PROFILE=llgenie-issse-implementer CHECK=1` reported the tree
copy behind again. Re-measured on `origin/main` @ `4aaac2c1`:

- **9 of 80 files differ**, every one LIVE-NEWER (tree is the truncated side — `live-longer` +
  `live-edited-not-tree`), all under
  `skills/software-development/llgenie-issue-to-pr/references/`.
- No `absent-from-tree` files; no `live-lines-missing` (none of the 9 is tree-ahead).
- Direction is therefore again **live→tree**: copy each differing live file into the tree
  byte-identically, so a rebuild cannot downgrade the lane.

## What this PR folds

- The 9 live-newer files copied live→tree byte-identically (raw-byte aggregate via
  `verify_fold_identity.py` / `cmp -s`): `acceptance-gate.md` (16,661→18,867 b),
  `gate-rerun-and-verify.md` (19,731→27,310 b), `mechanical-index-regeneration.md` (6,985→7,912 b),
  `pr-body-and-base-gates.md` (4,928→6,658 b), `pr-close-mismatch-recovery.md` (26,884→28,428 b),
  `squash-to-one-commit.md` (5,352→5,958 b), `stale-pr-head-and-self-proof.md` (7,269→8,357 b),
  `terminal-and-guard-pitfalls.md` (53,066→54,341 b), `wiring-and-forbidden-paths.md` (2,856→4,322 b).
- Live fold set was hash-stable across two polls before copying (no mid-write race); every copied
  file re-hashed to prove byte identity with its live source at the moment of the fold.

## Verification

- `make sync-agent-profile PROFILE=llgenie-issse-implementer CHECK=1` → **0 of 80 differ** at the
  pushed head (other lanes' rows are ambient host-side drift, out of scope for this vehicle).
- `scripts/verify_fold_identity.py` raw-byte aggregate `identical: True` against the committed blobs.
- Gates: `make check-agent-profiles` (same-lane rows == 0 across all four live classes), `make lint`,
  `make check-docs`, `make check-pr-closing` at the pushed head.
