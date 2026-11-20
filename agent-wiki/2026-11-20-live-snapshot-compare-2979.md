# 2026-11-20 — live comparisons run through one snapshot pass; findings name it (issue #2979)

Issue: #2979 (the `Not covered` half of #2972, landed by PR #2980). OpenSpec change:
`live-snapshot-compare`.

## What was verified

- The live-profile gates read a moving reference: a finding could be built from bytes that
  no longer exist by the time a human looks (#2972 measured 24,791 b vs 21,349 b on
  consecutive runs). `scripts/check_agent_profiles.py` now takes ONE snapshot per compared
  live file per run: `live_snapshot()` reads the file once and records content, size, mtime
  and the sha256 digest; `shrink_findings`, `live_edited_not_tree`, the absent-from-tree
  classes and `comparison_stats` all consume that record — the mtime in a finding is the
  snapshot's, the line-set compare decodes the snapshot's bytes, so size, mtime and content
  in one finding come from the SAME read.
- Every live-comparison finding names the snapshot: `live snapshot <sha12>` beside its size
  and mtime; the OK comparison line names the manifest — `snapshot manifest N file(s)
  digest <sha12>` (digest over the run's sorted path:digest pairs) — so a verdict is
  re-checkable against the exact manifest it compared.
- Mutation-after-snapshot is pinned by test: the live SOUL rewritten between two walks still
  renders the FIRST walk's digest and size; the rewrite's own size appears nowhere in the
  detail. The snapshot universe is cleared at `main()` so repeat runs/tests start clean.
- Exit-code semantics unchanged: red fixtures still exit 1, clean mirrors exit 0 (166 tests
  green across `tests/test_agent_profiles.py` + `tests/test_skill_parity.py`).

## Key decisions

- Digest, not content: the snapshot holds the bytes in memory for the run but prints only
  sha256 — a live profile holds credentials and the gate prints to a console.
- The stale-detection re-stat (`moved`) stays a live stat on purpose: it IS the moving
  detector; the snapshot pins what a finding reports, not whether the home is moving.
- The tree side keeps plain `stat()`/`read_bytes()`: the tree is checked out frozen; only
  the live side needed the snapshot.

## Current status

Landed via PR (closes #2979). `make profile-drift` / `check-agent-profiles` findings and OK
line now date AND identify the live state measured (#2972 stamps + #2979 digests).
